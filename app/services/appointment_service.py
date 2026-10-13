import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.exceptions import (
    ConcurrencyException,
    EntityNotFoundException,
    IdempotencyConflictException,
    IdempotencyPayloadMismatchException,
    SlotConflictException,
    ValidationException,
)
from app.domain.dispatch_policy import DispatchPolicy
from app.domain.state_machine import AppointmentStateMachine
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.idempotency_repo import IdempotencyRepository
from app.repositories.outbox_repo import OutboxRepository
from app.repositories.technician_repo import TechnicianRepository
from app.repositories.work_order_repo import WorkOrderRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
    AppointmentStatusUpdate,
    AppointmentUpdate,
    AvailableSlotsRequest,
    AvailableSlotsResponse,
    CancelAppointmentRequest,
    ConfirmBookingRequest,
    HoldSlotRequest,
    HoldSlotResponse,
    RescheduleAppointmentRequest,
    SlotOption,
)
from app.schemas.common import PaginatedResponse
from app.schemas.outbox import OutboxEventCreate, OutboxEventType


class AppointmentService:
    def __init__(
        self,
        appointment_repo: AppointmentRepository,
        technician_repo: TechnicianRepository,
        work_order_repo: WorkOrderRepository,
        audit_repo: AuditRepository,
        idempotency_repo: IdempotencyRepository,
        outbox_repo: OutboxRepository | None = None,
    ):
        self.appointment_repo = appointment_repo
        self.technician_repo = technician_repo
        self.work_order_repo = work_order_repo
        self.audit_repo = audit_repo
        self.idempotency_repo = idempotency_repo
        self.outbox_repo = outbox_repo or OutboxRepository(appointment_repo.db)

    @staticmethod
    def _generate_appt_number() -> str:
        year = datetime.now(UTC).year
        rand_num = random.randint(1000, 9999)
        return f"APT-{year}-{rand_num}"

    async def _stage_notification(
        self,
        event_type: OutboxEventType,
        appointment_id: str,
        customer_id: str,
        context: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> None:
        try:
            cust = await self.appointment_repo.db["customers"].find_one(
                {"_id": self.appointment_repo._to_object_id(customer_id)}
            )
            to_phone = cust.get("phone", "") if cust else ""
            to_email = cust.get("email", "") if cust else ""
            channel = cust.get("preferred_channel", "SMS") if cust else "SMS"

            await self.outbox_repo.stage_event(
                OutboxEventCreate(
                    event_type=event_type,
                    aggregate_type="Appointment",
                    aggregate_id=appointment_id,
                    payload={
                        "to_phone": to_phone,
                        "to_email": to_email,
                        "channel": channel,
                        "context": context,
                    },
                    idempotency_key=idempotency_key,
                )
            )
        except Exception:
            pass

    async def _stage_calendar_sync(
        self,
        appointment_id: str,
        title: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        location: str = "",
        external_event_id: str | None = None,
    ) -> None:
        try:
            await self.outbox_repo.stage_event(
                OutboxEventCreate(
                    event_type=OutboxEventType.CALENDAR_SYNC_EVENT,
                    aggregate_type="Appointment",
                    aggregate_id=appointment_id,
                    payload={
                        "title": title,
                        "start_time": scheduled_start,
                        "end_time": scheduled_end,
                        "location": location,
                        "external_calendar_event_id": external_event_id,
                    },
                    idempotency_key=f"cal_sync_{appointment_id}_{int(scheduled_start.timestamp())}",
                )
            )
        except Exception:
            pass

    # --- Slot Discovery ---
    async def get_available_slots(self, req: AvailableSlotsRequest) -> AvailableSlotsResponse:
        tz = ZoneInfo(req.timezone)
        target_dt = datetime.strptime(req.target_date, "%Y-%m-%d").replace(tzinfo=tz)
        target_day_name = target_dt.strftime("%A").upper()

        # Determine target technicians
        if req.technician_id:
            tech = await self.technician_repo.get_by_id(req.technician_id)
            if not tech:
                raise EntityNotFoundException("Technician", req.technician_id)
            technicians = [tech]
        elif req.work_order_id:
            wo = await self.work_order_repo.get_by_id(req.work_order_id)
            if not wo:
                raise EntityNotFoundException("WorkOrder", req.work_order_id)
            # Find active techs matching required skills
            all_active = await self.technician_repo.find_active()
            technicians = [
                t
                for t in all_active
                if DispatchPolicy.satisfies_skills(
                    t.get("skills", []), wo.get("required_skills", [])
                )
            ]
        else:
            technicians = await self.technician_repo.find_active()

        slot_options: list[SlotOption] = []
        day_start = target_dt.replace(hour=0, minute=0, second=0)
        day_end = target_dt.replace(hour=23, minute=59, second=59)

        for tech in technicians:
            tech_id = str(tech["id"])
            shift = DispatchPolicy.get_shift_for_day(tech.get("shift_schedule"), target_day_name)
            if not shift:
                continue

            shift_start, shift_end = shift
            shift_start_dt = target_dt.replace(
                hour=shift_start.hour, minute=shift_start.minute, second=0
            )
            shift_end_dt = target_dt.replace(hour=shift_end.hour, minute=shift_end.minute, second=0)

            # Query existing appointments for technician
            existing_appts = await self.appointment_repo.find_appointments_for_technician(
                technician_id=tech_id,
                start_date=day_start,
                end_date=day_end,
            )

            cursor = shift_start_dt
            step_minutes = 30

            while cursor + timedelta(minutes=req.duration_minutes) <= shift_end_dt:
                slot_end = cursor + timedelta(minutes=req.duration_minutes)

                # Check conflict against existing appointments with buffer
                has_conflict = False
                for appt in existing_appts:
                    appt_s = appt["scheduled_start"].astimezone(tz)
                    appt_e = appt["scheduled_end"].astimezone(tz)
                    if (
                        cursor - timedelta(minutes=req.buffer_minutes) < appt_e
                        and slot_end + timedelta(minutes=req.buffer_minutes) > appt_s
                    ):
                        has_conflict = True
                        break

                if not has_conflict:
                    start_str = cursor.strftime("%I:%M %p")
                    end_str = slot_end.strftime("%I:%M %p")
                    tz_abbr = cursor.strftime("%Z")
                    slot_options.append(
                        SlotOption(
                            start_time=cursor.astimezone(UTC),
                            end_time=slot_end.astimezone(UTC),
                            technician_id=tech_id,
                            technician_name=tech["name"],
                            formatted_time_window=f"{start_str} - {end_str} {tz_abbr}",
                        )
                    )

                cursor += timedelta(minutes=step_minutes)

        return AvailableSlotsResponse(
            target_date=req.target_date,
            timezone=req.timezone,
            slots=slot_options,
        )

    # --- Ephemeral Hold ---
    async def hold_slot(self, req: HoldSlotRequest) -> HoldSlotResponse:
        tech = await self.technician_repo.get_by_id(req.technician_id)
        if not tech:
            raise EntityNotFoundException("Technician", req.technician_id)

        wo = await self.work_order_repo.get_by_id(req.work_order_id)
        if not wo:
            raise EntityNotFoundException("WorkOrder", req.work_order_id)

        token = f"res_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=10)

        # Database-enforced atomic conditional reservation
        reserved = await self.technician_repo.add_active_booking_atomic(
            technician_id=req.technician_id,
            booking_id=token,
            start_time=req.scheduled_start,
            end_time=req.scheduled_end,
            status="TENTATIVE_HOLD",
            buffer_minutes=0,  # holds reserve the exact window
        )
        if not reserved:
            raise SlotConflictException(
                technician_id=req.technician_id,
                scheduled_start=req.scheduled_start.isoformat(),
            )

        # Store in slot_reservations collection
        res_doc = {
            "reservation_token": token,
            "technician_id": req.technician_id,
            "work_order_id": req.work_order_id,
            "customer_id": req.customer_id,
            "scheduled_start": req.scheduled_start,
            "scheduled_end": req.scheduled_end,
            "created_at": now,
            "expires_at": expires_at,
            "status": "HELD",
        }
        await self.technician_repo.db["slot_reservations"].insert_one(res_doc)

        return HoldSlotResponse(
            reservation_token=token,
            technician_id=req.technician_id,
            work_order_id=req.work_order_id,
            scheduled_start=req.scheduled_start,
            scheduled_end=req.scheduled_end,
            expires_at=expires_at,
            status="TENTATIVE_HOLD",
        )

    # --- Confirm Booking ---
    async def confirm_booking(self, req: ConfirmBookingRequest) -> AppointmentResponse:
        # 1. Require explicit confirmation
        if not req.user_confirmed:
            raise ValidationException(
                "Explicit customer confirmation is required before finalizing an appointment booking."
            )

        # 2. Idempotency handling
        key = req.idempotency_key
        payload_data = req.model_dump(mode="json", exclude={"idempotency_key"})
        request_hash = self.idempotency_repo.compute_request_hash(payload_data)

        if key:
            acquired, existing = await self.idempotency_repo.acquire(
                key=key, scope="appointment_confirm", request_hash=request_hash
            )
            if not acquired and existing:
                if existing.get("status") == "COMPLETED":
                    if existing.get("request_hash") != request_hash:
                        raise IdempotencyPayloadMismatchException(key)
                    return AppointmentResponse(**existing["response_body"])
                elif existing.get("status") == "PENDING":
                    raise IdempotencyConflictException(key)

        # 3. Check if an appointment was ALREADY confirmed for this reservation token (Safe Idempotent Retry)
        existing_appt = await self.appointment_repo.get_by_reservation_token(req.reservation_token)
        if existing_appt:
            response_obj = AppointmentResponse(**existing_appt)
            if key:
                await self.idempotency_repo.commit(
                    key=key,
                    scope="appointment_confirm",
                    response_code=201,
                    response_body=response_obj.model_dump(mode="json"),
                )
            return response_obj

        try:
            # 4. Retrieve reservation hold document
            reservation = await self.technician_repo.db["slot_reservations"].find_one(
                {"reservation_token": req.reservation_token}
            )
            if not reservation:
                # Re-check if appointment was confirmed by concurrent caller just now
                existing_appt = await self.appointment_repo.get_by_reservation_token(
                    req.reservation_token
                )
                if existing_appt:
                    response_obj = AppointmentResponse(**existing_appt)
                    if key:
                        await self.idempotency_repo.commit(
                            key=key,
                            scope="appointment_confirm",
                            response_code=201,
                            response_body=response_obj.model_dump(mode="json"),
                        )
                    return response_obj

                # If hold document is purged by TTL or missing, release any orphan hold on technician
                tech_with_hold = await self.technician_repo.collection.find_one(
                    {"active_bookings.booking_id": req.reservation_token}
                )
                if tech_with_hold:
                    await self.technician_repo.remove_active_booking(
                        str(tech_with_hold["_id"]), req.reservation_token
                    )

                raise ValidationException(
                    "Reservation hold has expired or is invalid. Please select a new slot."
                )

            # Check expiration before proceeding
            now = datetime.now(UTC)
            expires_at = reservation.get("expires_at", now)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < now:
                # Expired hold: release from tech calendar and clean up hold record
                await self.technician_repo.remove_active_booking(
                    reservation["technician_id"], req.reservation_token
                )
                await self.technician_repo.db["slot_reservations"].delete_one(
                    {"reservation_token": req.reservation_token}
                )
                raise ValidationException(
                    "Reservation hold has expired (10-minute window passed). Please select a new slot."
                )

            # Atomically claim reservation hold using lease-based state machine
            claim_lease = now + timedelta(seconds=30)
            claim_id = str(uuid.uuid4())
            claimed = await self.technician_repo.db["slot_reservations"].find_one_and_update(
                {
                    "_id": reservation["_id"],
                    "status": {"$in": ["HELD", "CONFIRMING"]},
                },
                {
                    "$set": {
                        "status": "CONFIRMING",
                        "claim_id": claim_id,
                        "claim_expires_at": claim_lease,
                        "updated_at": now,
                    }
                },
            )
            if not claimed:
                existing_appt = await self.appointment_repo.get_by_reservation_token(
                    req.reservation_token
                )
                if existing_appt:
                    response_obj = AppointmentResponse(**existing_appt)
                    if key:
                        await self.idempotency_repo.commit(
                            key=key,
                            scope="appointment_confirm",
                            response_code=201,
                            response_body=response_obj.model_dump(mode="json"),
                        )
                    return response_obj
                raise ConcurrencyException(
                    "Appointment reservation hold is currently being claimed by another process."
                )

            # 5. Create confirmed appointment
            appt_number = self._generate_appt_number()
            sched_start = reservation["scheduled_start"]
            if sched_start and sched_start.tzinfo is None:
                sched_start = sched_start.replace(tzinfo=UTC)
            sched_end = reservation["scheduled_end"]
            if sched_end and sched_end.tzinfo is None:
                sched_end = sched_end.replace(tzinfo=UTC)

            appt_doc = {
                "appointment_number": appt_number,
                "work_order_id": reservation["work_order_id"],
                "technician_id": reservation["technician_id"],
                "customer_id": reservation["customer_id"],
                "scheduled_start": sched_start,
                "scheduled_end": sched_end,
                "customer_notes": req.customer_notes,
                "status": "CONFIRMED",
                "lock_version": 1,
                "reservation_token": req.reservation_token,
                "created_at": now,
                "updated_at": now,
            }
            try:
                created_appt = await self.appointment_repo.create(appt_doc)
            except Exception:
                # If concurrent write succeeded with same token, recover existing
                existing_appt = await self.appointment_repo.get_by_reservation_token(
                    req.reservation_token
                )
                if existing_appt:
                    return AppointmentResponse(**existing_appt)
                raise

            # 6. Update technician booking status from TENTATIVE_HOLD to CONFIRMED
            await self.technician_repo.collection.update_one(
                {
                    "_id": self.technician_repo._to_object_id(reservation["technician_id"]),
                    "active_bookings.booking_id": req.reservation_token,
                },
                {
                    "$set": {
                        "active_bookings.$.status": "CONFIRMED",
                        "active_bookings.$.appointment_id": created_appt["id"],
                    }
                },
            )

            # 7. Update work order
            await self.work_order_repo.update(
                reservation["work_order_id"],
                {
                    "active_appointment_id": created_appt["id"],
                    "assigned_technician_id": reservation["technician_id"],
                    "status": "SCHEDULED",
                },
            )

            # 8. Clean up reservation hold document
            await self.technician_repo.db["slot_reservations"].delete_one(
                {"reservation_token": req.reservation_token}
            )

            # 9. Log audit event
            await self.audit_repo.log_event(
                entity_type="Appointment",
                entity_id=created_appt["id"],
                action="CONFIRM_BOOKING",
                changes={"status": "CONFIRMED"},
                metadata={"work_order_id": reservation["work_order_id"]},
            )

            # 10. Stage transactional outbox events
            sched_start = created_appt["scheduled_start"]
            tech = await self.technician_repo.get_by_id(reservation["technician_id"])
            wo = await self.work_order_repo.get_by_id(reservation["work_order_id"])
            tech_name = (
                tech.get("name", "Field Technician")
                if isinstance(tech, dict)
                else getattr(tech, "name", "Field Technician")
                if tech
                else "Field Technician"
            )
            wo_category = (
                wo.get("category", "General Service")
                if isinstance(wo, dict)
                else getattr(wo, "category", "General Service")
                if wo
                else "General Service"
            )
            await self._stage_notification(
                event_type=OutboxEventType.NOTIFICATION_BOOKING_CONFIRMED,
                appointment_id=created_appt["id"],
                customer_id=reservation["customer_id"],
                context={
                    "scheduled_time": sched_start.strftime("%A, %b %d at %I:%M %p"),
                    "scheduled_date": sched_start.strftime("%Y-%m-%d"),
                    "technician_name": tech_name,
                    "category": wo_category,
                    "tracking_url": f"https://fieldops.ai/appointments/{created_appt['id']}",
                },
                idempotency_key=f"notif_confirm_{created_appt['id']}",
            )
            await self._stage_calendar_sync(
                appointment_id=created_appt["id"],
                title=f"Field Service: {wo_category} Appointment",
                scheduled_start=created_appt["scheduled_start"],
                scheduled_end=created_appt["scheduled_end"],
            )

            response_obj = AppointmentResponse(**created_appt)

            # Commit idempotency
            if key:
                await self.idempotency_repo.commit(
                    key=key,
                    scope="appointment_confirm",
                    response_code=201,
                    response_body=response_obj.model_dump(mode="json"),
                )

            return response_obj

        except Exception:
            if key:
                await self.idempotency_repo.release(key=key, scope="appointment_confirm")
            # If appointment wasn't created yet, revert reservation claim from CONFIRMING back to HELD
            existing_appt = await self.appointment_repo.get_by_reservation_token(
                req.reservation_token
            )
            if not existing_appt:
                await self.technician_repo.db["slot_reservations"].update_one(
                    {"reservation_token": req.reservation_token, "status": "CONFIRMING"},
                    {
                        "$set": {"status": "HELD"},
                        "$unset": {"claim_id": "", "claim_expires_at": ""},
                    },
                )
            raise

    # --- Direct Create (Backwards Compatibility & Manual Override) ---
    async def create_appointment(self, appt_in: AppointmentCreate) -> AppointmentResponse:
        from bson import ObjectId

        tech = await self.technician_repo.get_by_id(appt_in.technician_id)
        if not tech:
            raise EntityNotFoundException("Technician", appt_in.technician_id)

        wo = await self.work_order_repo.get_by_id(appt_in.work_order_id)
        if not wo:
            raise EntityNotFoundException("WorkOrder", appt_in.work_order_id)

        pre_id = str(ObjectId())

        # Database-enforced atomic conditional reservation
        reserved = await self.technician_repo.add_active_booking_atomic(
            technician_id=appt_in.technician_id,
            booking_id=pre_id,
            start_time=appt_in.scheduled_start,
            end_time=appt_in.scheduled_end,
            status=appt_in.status.value,
            buffer_minutes=0,
        )
        if not reserved:
            raise SlotConflictException(
                technician_id=appt_in.technician_id,
                scheduled_start=appt_in.scheduled_start.isoformat(),
            )

        doc_data = appt_in.model_dump()
        doc_data["_id"] = ObjectId(pre_id)
        doc_data["appointment_number"] = self._generate_appt_number()
        doc_data["lock_version"] = 1
        created = await self.appointment_repo.create(doc_data)

        # Link appointment to work order
        await self.work_order_repo.update(
            appt_in.work_order_id,
            {
                "active_appointment_id": created["id"],
                "assigned_technician_id": appt_in.technician_id,
                "status": "SCHEDULED",
            },
        )

        await self.audit_repo.log_event(
            entity_type="Appointment",
            entity_id=created["id"],
            action="CREATE",
            changes={"status": appt_in.status.value},
            metadata={"work_order_id": appt_in.work_order_id},
        )

        # Stage transactional outbox events
        tech_name = (
            tech.get("name", "Field Technician")
            if isinstance(tech, dict)
            else getattr(tech, "name", "Field Technician")
            if tech
            else "Field Technician"
        )
        wo_category = (
            wo.get("category", "General Service")
            if isinstance(wo, dict)
            else getattr(wo, "category", "General Service")
            if wo
            else "General Service"
        )
        await self._stage_notification(
            event_type=OutboxEventType.NOTIFICATION_BOOKING_CONFIRMED,
            appointment_id=created["id"],
            customer_id=appt_in.customer_id,
            context={
                "scheduled_time": appt_in.scheduled_start.strftime("%A, %b %d at %I:%M %p"),
                "scheduled_date": appt_in.scheduled_start.strftime("%Y-%m-%d"),
                "technician_name": tech_name,
                "category": wo_category,
                "tracking_url": f"https://fieldops.ai/appointments/{created['id']}",
            },
            idempotency_key=f"notif_confirm_{created['id']}",
        )
        await self._stage_calendar_sync(
            appointment_id=created["id"],
            title=f"Field Service: {wo_category} Appointment",
            scheduled_start=appt_in.scheduled_start,
            scheduled_end=appt_in.scheduled_end,
        )

        return AppointmentResponse(**created)

    async def get_appointment(self, appointment_id: str) -> AppointmentResponse:
        doc = await self.appointment_repo.get_by_id(appointment_id)
        if not doc:
            raise EntityNotFoundException("Appointment", appointment_id)
        return AppointmentResponse(**doc)

    async def list_appointments(
        self,
        technician_id: str | None = None,
        customer_id: str | None = None,
        status: AppointmentStatus | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedResponse[AppointmentResponse]:
        skip = (page - 1) * limit
        filter_query = {}
        if technician_id:
            filter_query["technician_id"] = technician_id
        if customer_id:
            filter_query["customer_id"] = customer_id
        if status:
            filter_query["status"] = status.value

        items, total = await self.appointment_repo.get_many(
            filter_query, skip=skip, limit=limit, sort_field="scheduled_start", sort_order=1
        )
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        return PaginatedResponse(
            items=[AppointmentResponse(**item) for item in items],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    # --- Cancellation ---
    async def cancel_appointment(
        self, appointment_id: str, req: CancelAppointmentRequest
    ) -> AppointmentResponse:
        appt = await self.get_appointment(appointment_id)
        current_status = AppointmentStatus(appt.status)

        AppointmentStateMachine.validate_transition(current_status, AppointmentStatus.CANCELLED)

        # 1. Update appointment status using optimistic concurrency control
        updated = await self.appointment_repo.update_with_lock(
            appointment_id,
            appt.lock_version,
            {
                "status": AppointmentStatus.CANCELLED.value,
                "cancellation_reason": req.reason,
                "lock_version": appt.lock_version + 1,
            },
        )
        if not updated:
            raise ConcurrencyException(f"Appointment {appointment_id} was modified concurrently.")

        # 2. Release active booking from technician document
        await self.technician_repo.remove_active_booking(
            technician_id=appt.technician_id,
            booking_id=appointment_id,
        )

        # 3. Log audit event
        await self.audit_repo.log_event(
            entity_type="Appointment",
            entity_id=appointment_id,
            action="CANCEL",
            actor_id=req.actor_id,
            changes={"status": AppointmentStatus.CANCELLED.value},
            metadata={"reason": req.reason},
        )

        # 4. Stage outbox notification
        await self._stage_notification(
            event_type=OutboxEventType.NOTIFICATION_APPOINTMENT_CANCELLED,
            appointment_id=appointment_id,
            customer_id=appt.customer_id,
            context={
                "scheduled_time": appt.scheduled_start.strftime("%A, %b %d at %I:%M %p"),
                "scheduled_date": appt.scheduled_start.strftime("%Y-%m-%d"),
                "reason": req.reason or "Customer requested cancellation.",
                "tracking_url": f"https://fieldops.ai/appointments/{appointment_id}",
            },
            idempotency_key=f"notif_cancel_{appointment_id}",
        )

        return AppointmentResponse(**updated)  # type: ignore

    # --- Rescheduling ---
    async def reschedule_appointment(
        self, appointment_id: str, req: RescheduleAppointmentRequest
    ) -> AppointmentResponse:
        appt = await self.get_appointment(appointment_id)
        current_status = AppointmentStatus(appt.status)

        AppointmentStateMachine.validate_transition(current_status, AppointmentStatus.RESCHEDULED)

        target_tech_id = req.technician_id or appt.technician_id

        # 1. Release previous booking first so the technician's calendar opens up
        await self.technician_repo.remove_active_booking(
            technician_id=appt.technician_id,
            booking_id=appointment_id,
        )

        # 2. Database-enforced atomic reservation on target technician using appointment_id
        reserved = await self.technician_repo.add_active_booking_atomic(
            technician_id=target_tech_id,
            booking_id=appointment_id,
            start_time=req.new_scheduled_start,
            end_time=req.new_scheduled_end,
            status="CONFIRMED",
            buffer_minutes=0,
        )
        if not reserved:
            # Revert previous booking if new slot had conflict
            await self.technician_repo.add_active_booking_atomic(
                technician_id=appt.technician_id,
                booking_id=appointment_id,
                start_time=appt.scheduled_start,
                end_time=appt.scheduled_end,
                status="CONFIRMED",
                buffer_minutes=0,
            )
            raise SlotConflictException(
                technician_id=target_tech_id,
                scheduled_start=req.new_scheduled_start.isoformat(),
            )

        # 3. Update appointment record with optimistic locking
        update_data = {
            "scheduled_start": req.new_scheduled_start,
            "scheduled_end": req.new_scheduled_end,
            "technician_id": target_tech_id,
            "status": AppointmentStatus.CONFIRMED.value,
            "reschedule_reason": req.reason,
            "lock_version": appt.lock_version + 1,
        }
        updated = await self.appointment_repo.update_with_lock(
            appointment_id, appt.lock_version, update_data
        )
        if not updated:
            # Revert booked slot if concurrent update changed version
            await self.technician_repo.remove_active_booking(target_tech_id, appointment_id)
            await self.technician_repo.add_active_booking_atomic(
                technician_id=appt.technician_id,
                booking_id=appointment_id,
                start_time=appt.scheduled_start,
                end_time=appt.scheduled_end,
                status="CONFIRMED",
                buffer_minutes=0,
            )
            raise ConcurrencyException(f"Appointment {appointment_id} was modified concurrently.")

        # Update work order assigned technician if changed
        if target_tech_id != appt.technician_id:
            await self.work_order_repo.update(
                appt.work_order_id, {"assigned_technician_id": target_tech_id}
            )

        await self.audit_repo.log_event(
            entity_type="Appointment",
            entity_id=appointment_id,
            action="RESCHEDULE",
            changes=update_data,
            metadata={"reason": req.reason},
        )

        # Stage outbox notification and calendar sync
        tech = await self.technician_repo.get_by_id(target_tech_id)
        tech_name = (
            tech.get("name", "Field Technician")
            if isinstance(tech, dict)
            else getattr(tech, "name", "Field Technician")
            if tech
            else "Field Technician"
        )
        await self._stage_notification(
            event_type=OutboxEventType.NOTIFICATION_APPOINTMENT_RESCHEDULED,
            appointment_id=appointment_id,
            customer_id=appt.customer_id,
            context={
                "new_scheduled_time": req.new_scheduled_start.strftime("%A, %b %d at %I:%M %p"),
                "technician_name": tech_name,
                "reason": req.reason or "Rescheduled",
                "tracking_url": f"https://fieldops.ai/appointments/{appointment_id}",
            },
            idempotency_key=f"notif_resched_{appointment_id}_{appt.lock_version + 1}",
        )
        await self._stage_calendar_sync(
            appointment_id=appointment_id,
            title="Field Service: Rescheduled Appointment",
            scheduled_start=req.new_scheduled_start,
            scheduled_end=req.new_scheduled_end,
        )

        return AppointmentResponse(**updated)  # type: ignore

    async def transition_status(
        self, appointment_id: str, status_in: AppointmentStatusUpdate
    ) -> AppointmentResponse:
        current_appt = await self.get_appointment(appointment_id)
        current_status = AppointmentStatus(current_appt.status)
        new_status = status_in.new_status

        # Validate domain state machine
        AppointmentStateMachine.validate_transition(current_status, new_status)

        update_payload = {"status": new_status.value}
        now = datetime.now(UTC)
        if new_status == AppointmentStatus.ON_SITE and not current_appt.actual_start:
            update_payload["actual_start"] = now
        elif new_status == AppointmentStatus.COMPLETED and not current_appt.actual_end:
            update_payload["actual_end"] = now

        # If terminal state completed/cancelled, release booking from active list
        if new_status in (
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        ):
            await self.technician_repo.remove_active_booking(
                technician_id=current_appt.technician_id,
                booking_id=appointment_id,
            )

        updated = await self.appointment_repo.update(appointment_id, update_payload)

        await self.audit_repo.log_event(
            entity_type="Appointment",
            entity_id=appointment_id,
            action="TRANSITION_STATUS",
            actor_id=status_in.actor_id,
            changes={"from": current_status.value, "to": new_status.value},
            metadata={"reason": status_in.reason},
        )

        return AppointmentResponse(**updated)  # type: ignore

    async def update_appointment(
        self, appointment_id: str, appt_in: AppointmentUpdate
    ) -> AppointmentResponse:
        current = await self.get_appointment(appointment_id)
        update_data = appt_in.model_dump(exclude_unset=True)

        if appt_in.scheduled_start or appt_in.scheduled_end or appt_in.technician_id:
            reschedule_req = RescheduleAppointmentRequest(
                new_scheduled_start=appt_in.scheduled_start or current.scheduled_start,
                new_scheduled_end=appt_in.scheduled_end or current.scheduled_end,
                technician_id=appt_in.technician_id or current.technician_id,
                reason="Direct appointment update",
            )
            return await self.reschedule_appointment(appointment_id, reschedule_req)

        updated = await self.appointment_repo.update(appointment_id, update_data)
        return AppointmentResponse(**updated)  # type: ignore

    async def reconcile_inconsistent_bookings(self) -> dict[str, int]:
        """
        Reconciles any stranded reservation holds or partially completed confirmations:
        - Stranded 'CONFIRMING' holds where an appointment was created -> completes technician & work order sync.
        - Stranded 'CONFIRMING' holds with no appointment and expired lease -> reverts to 'HELD' (or releases expired hold).
        - Expired 'HELD' reservations past expires_at -> releases technician active booking and deletes hold document.
        """
        now = datetime.now(UTC)
        repaired_confirmed = 0
        repaired_released = 0

        # 1. Check slot_reservations stuck in CONFIRMING
        cursor = self.technician_repo.db["slot_reservations"].find(
            {
                "status": "CONFIRMING",
                "claim_expires_at": {"$lt": now},
            }
        )
        async for res in cursor:
            token = res.get("reservation_token")
            existing_appt = await self.appointment_repo.get_by_reservation_token(token)
            if existing_appt:
                # Appointment exists: ensure technician and work order are in sync
                await self.technician_repo.collection.update_one(
                    {
                        "_id": self.technician_repo._to_object_id(res["technician_id"]),
                        "active_bookings.booking_id": token,
                    },
                    {
                        "$set": {
                            "active_bookings.$.status": "CONFIRMED",
                            "active_bookings.$.appointment_id": existing_appt["id"],
                        }
                    },
                )
                await self.work_order_repo.update(
                    res["work_order_id"],
                    {
                        "active_appointment_id": existing_appt["id"],
                        "assigned_technician_id": res["technician_id"],
                        "status": "SCHEDULED",
                    },
                )
                await self.technician_repo.db["slot_reservations"].delete_one({"_id": res["_id"]})
                repaired_confirmed += 1
            else:
                exp = res.get("expires_at", now)
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=UTC)
                if exp < now:
                    await self.technician_repo.remove_active_booking(res["technician_id"], token)
                    await self.technician_repo.db["slot_reservations"].delete_one(
                        {"_id": res["_id"]}
                    )
                    repaired_released += 1
                else:
                    await self.technician_repo.db["slot_reservations"].update_one(
                        {"_id": res["_id"]},
                        {
                            "$set": {"status": "HELD"},
                            "$unset": {"claim_id": "", "claim_expires_at": ""},
                        },
                    )

        # 2. Check expired HELD reservations
        expired_cursor = self.technician_repo.db["slot_reservations"].find(
            {
                "status": "HELD",
                "expires_at": {"$lt": now},
            }
        )
        async for exp_res in expired_cursor:
            token = exp_res.get("reservation_token")
            await self.technician_repo.remove_active_booking(exp_res["technician_id"], token)
            await self.technician_repo.db["slot_reservations"].delete_one({"_id": exp_res["_id"]})
            repaired_released += 1

        return {"repaired_confirmed": repaired_confirmed, "repaired_released": repaired_released}

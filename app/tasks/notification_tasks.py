import logging
from datetime import UTC, datetime, timedelta

from app.core.celery_app import celery_app
from app.core.database import db_manager
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.outbox_repo import OutboxRepository
from app.repositories.technician_repo import TechnicianRepository
from app.repositories.work_order_repo import WorkOrderRepository
from app.schemas.outbox import OutboxEventCreate, OutboxEventType
from app.tasks.utils import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.notification_tasks.check_upcoming_appointment_reminders_task")
def check_upcoming_appointment_reminders_task() -> dict[str, int]:
    """
    Scans upcoming confirmed appointments to stage 24-hour and 2-hour reminders.
    """

    async def _scan():
        db = db_manager.get_database()
        appt_repo = AppointmentRepository(db)
        cust_repo = CustomerRepository(db)
        tech_repo = TechnicianRepository(db)
        wo_repo = WorkOrderRepository(db)
        outbox_repo = OutboxRepository(db)

        now = datetime.now(UTC)
        reminders_staged = 0

        # 1. Check 24-hour window (23 to 25 hours ahead)
        w24_start = now + timedelta(hours=23)
        w24_end = now + timedelta(hours=25)
        cursor_24h = appt_repo.collection.find(
            {
                "status": "CONFIRMED",
                "scheduled_start": {"$gte": w24_start, "$lte": w24_end},
                "reminder_24h_sent": {"$ne": True},
            }
        )

        async for appt in cursor_24h:
            customer = await cust_repo.get_by_id(appt["customer_id"])
            technician = await tech_repo.get_by_id(appt["technician_id"])
            work_order = await wo_repo.get_by_id(appt["work_order_id"])

            if customer:
                context = {
                    "customer_name": customer.name
                    if hasattr(customer, "name")
                    else customer.full_name,
                    "scheduled_time": appt["scheduled_start"].strftime("%A, %b %d at %I:%M %p"),
                    "technician_name": technician.name if technician else "Field Technician",
                    "category": work_order.category if work_order else "Maintenance",
                    "service_address": f"{customer.service_addresses[0].street}, {customer.service_addresses[0].city}"
                    if customer.service_addresses
                    else "",
                    "tracking_url": f"https://fieldops.ai/appointments/{appt['_id']}",
                }
                event_create = OutboxEventCreate(
                    event_type=OutboxEventType.NOTIFICATION_REMINDER_24H,
                    aggregate_type="Appointment",
                    aggregate_id=str(appt["_id"]),
                    payload={
                        "to_phone": customer.phone,
                        "to_email": customer.email,
                        "channel": customer.preferred_channel or "SMS",
                        "context": context,
                    },
                    idempotency_key=f"remind_24h_{appt['_id']}",
                )
                await outbox_repo.stage_event(event_create)
                await appt_repo.update(str(appt["_id"]), {"reminder_24h_sent": True})
                reminders_staged += 1

        # 2. Check 2-hour window (1h 45m to 2h 15m ahead)
        w2_start = now + timedelta(minutes=105)
        w2_end = now + timedelta(minutes=135)
        cursor_2h = appt_repo.collection.find(
            {
                "status": "CONFIRMED",
                "scheduled_start": {"$gte": w2_start, "$lte": w2_end},
                "reminder_2h_sent": {"$ne": True},
            }
        )

        async for appt in cursor_2h:
            customer = await cust_repo.get_by_id(appt["customer_id"])
            technician = await tech_repo.get_by_id(appt["technician_id"])
            work_order = await wo_repo.get_by_id(appt["work_order_id"])

            if customer:
                context = {
                    "customer_name": customer.name
                    if hasattr(customer, "name")
                    else customer.full_name,
                    "scheduled_time": appt["scheduled_start"].strftime("%I:%M %p"),
                    "technician_name": technician.name if technician else "Field Technician",
                    "category": work_order.category if work_order else "Maintenance",
                    "service_address": f"{customer.service_addresses[0].street}, {customer.service_addresses[0].city}"
                    if customer.service_addresses
                    else "",
                    "tracking_url": f"https://fieldops.ai/appointments/{appt['_id']}",
                }
                event_create = OutboxEventCreate(
                    event_type=OutboxEventType.NOTIFICATION_REMINDER_2H,
                    aggregate_type="Appointment",
                    aggregate_id=str(appt["_id"]),
                    payload={
                        "to_phone": customer.phone,
                        "to_email": customer.email,
                        "channel": customer.preferred_channel or "SMS",
                        "context": context,
                    },
                    idempotency_key=f"remind_2h_{appt['_id']}",
                )
                await outbox_repo.stage_event(event_create)
                await appt_repo.update(str(appt["_id"]), {"reminder_2h_sent": True})
                reminders_staged += 1

        return {"reminders_staged": reminders_staged}

    return run_async(_scan())

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import EntityNotFoundException
from app.domain.dispatch_policy import DispatchPolicy, DispatchWeights
from app.integrations.maps.protocol import MapsProviderProtocol
from app.ml.schemas import JobDurationPredictionRequest, MissedAppointmentRiskRequest
from app.ml.service import MLPredictionService, get_ml_service
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.technician_repo import TechnicianRepository
from app.repositories.work_order_repo import WorkOrderRepository
from app.schemas.dispatch import (
    MatchCandidatesRequest,
    MatchCandidatesResponse,
    TechnicianCandidateResponse,
)
from app.schemas.work_order import WorkOrderResponse

logger = logging.getLogger(__name__)


class DispatchService:
    def __init__(
        self,
        technician_repo: TechnicianRepository,
        work_order_repo: WorkOrderRepository,
        appointment_repo: AppointmentRepository,
        maps_adapter: MapsProviderProtocol,
        ml_service: MLPredictionService | None = None,
    ):
        self.technician_repo = technician_repo
        self.work_order_repo = work_order_repo
        self.appointment_repo = appointment_repo
        self.maps_adapter = maps_adapter
        try:
            self.ml_service = ml_service or get_ml_service()
        except Exception:
            self.ml_service = None

    async def match_candidates(self, request: MatchCandidatesRequest) -> MatchCandidatesResponse:
        # 1. Fetch work order
        wo_doc = await self.work_order_repo.get_by_id(request.work_order_id)
        if not wo_doc:
            raise EntityNotFoundException("WorkOrder", request.work_order_id)
        work_order = WorkOrderResponse(**wo_doc)

        # 2. Determine target date
        if request.target_date:
            target_date_str = request.target_date
        elif work_order.preferred_time_window and work_order.preferred_time_window.preferred_date:
            target_date_str = work_order.preferred_time_window.preferred_date
        else:
            # Default to tomorrow
            target_date_str = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")

        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").replace(
            tzinfo=ZoneInfo("America/New_York")
        )
        target_day_name = target_dt.strftime("%A").upper()

        weights = DispatchWeights.from_dict(request.weights)

        # 3. Destination coordinates
        dest_coords = [-84.3880, 33.7490]  # default Atlanta
        if work_order.service_address.location and work_order.service_address.location.coordinates:
            dest_coords = work_order.service_address.location.coordinates
        else:
            # Geocode via maps adapter
            addr_str = f"{work_order.service_address.street}, {work_order.service_address.city}"
            dest_coords = await self.maps_adapter.geocode_address(addr_str)

        # 4. Fetch all active technicians
        all_techs = await self.technician_repo.find_active()

        candidates: list[TechnicianCandidateResponse] = []

        # Target date boundaries for active jobs count
        day_start = target_dt.replace(hour=0, minute=0, second=0)
        day_end = target_dt.replace(hour=23, minute=59, second=59)

        for tech in all_techs:
            # Hard filter 1: Required Skills
            if not DispatchPolicy.satisfies_skills(
                tech.get("skills", []), work_order.required_skills
            ):
                continue

            # Hard filter 2: Working Shift
            shift = DispatchPolicy.get_shift_for_day(tech.get("shift_schedule"), target_day_name)
            if not shift:
                continue

            # Calculate travel distance & drive time
            origin = (
                tech.get("current_location", {}).get("coordinates")
                or tech.get("home_base", {}).get("coordinates")
                or [-84.3880, 33.7490]
            )
            dist_res = await self.maps_adapter.calculate_distance(origin, dest_coords)

            # Hard filter 3: Service Area Radius
            max_radius = float(tech.get("max_travel_radius_km", 40.0))
            if not DispatchPolicy.satisfies_service_area(dist_res.distance_km, max_radius):
                continue

            # Hard filter 4: Working capacity & schedule
            existing_appts = await self.appointment_repo.find_appointments_for_technician(
                technician_id=str(tech["id"]),
                start_date=day_start,
                end_date=day_end,
            )
            active_jobs_count = len(existing_appts)

            # Generate available candidate start times within shift
            shift_start, shift_end = shift
            shift_start_dt = target_dt.replace(
                hour=shift_start.hour, minute=shift_start.minute, second=0
            )
            shift_end_dt = target_dt.replace(hour=shift_end.hour, minute=shift_end.minute, second=0)

            # Discover available slots
            est_duration = work_order.estimated_duration_minutes
            step_minutes = 30
            cursor = shift_start_dt
            available_slots = []

            while cursor + timedelta(minutes=est_duration) <= shift_end_dt:
                slot_end = cursor + timedelta(minutes=est_duration)
                # Check for overlap with existing bookings (including 30 min buffer)
                has_overlap = False
                for appt in existing_appts:
                    appt_s = appt["scheduled_start"].astimezone(ZoneInfo("America/New_York"))
                    appt_e = appt["scheduled_end"].astimezone(ZoneInfo("America/New_York"))
                    if (
                        cursor - timedelta(minutes=30) < appt_e
                        and slot_end + timedelta(minutes=30) > appt_s
                    ):
                        has_overlap = True
                        break
                if not has_overlap:
                    available_slots.append(cursor)
                cursor += timedelta(minutes=step_minutes)

            # Predict duration and missed risk via ML
            ml_duration_minutes: float | None = None
            ml_risk_prob: float | None = None
            if self.ml_service:
                try:
                    category_val = (
                        work_order.category.value
                        if hasattr(work_order.category, "value")
                        else str(work_order.category)
                    )
                    urgency_val = (
                        work_order.priority.value
                        if hasattr(work_order.priority, "value")
                        else str(work_order.priority)
                    )
                    dur_pred = self.ml_service.predict_job_duration(
                        JobDurationPredictionRequest(
                            category=category_val,
                            urgency=urgency_val,
                            technician_experience_years=float(tech.get("experience_years", 3.0)),
                            technician_active_jobs_count=active_jobs_count,
                            distance_km=dist_res.distance_km,
                            estimated_duration_minutes=work_order.estimated_duration_minutes,
                        )
                    )
                    ml_duration_minutes = dur_pred.predicted_duration_minutes

                    risk_pred = self.ml_service.predict_missed_appointment_risk(
                        MissedAppointmentRiskRequest(
                            category=category_val,
                            scheduled_hour_of_day=shift_start.hour,
                            scheduled_day_of_week=target_dt.weekday(),
                            travel_distance_km=dist_res.distance_km,
                            technician_experience_years=float(tech.get("experience_years", 3.0)),
                            urgency=urgency_val,
                        )
                    )
                    ml_risk_prob = risk_pred.risk_probability
                except Exception as e:
                    logger.debug("ML candidate score adjustment skipped: %s", e)

            # Score candidate using DispatchPolicy
            candidate_resp = DispatchPolicy.score_candidate(
                technician=tech,
                work_order=work_order,
                distance_km=dist_res.distance_km,
                drive_time_minutes=dist_res.duration_minutes,
                active_jobs_count=active_jobs_count,
                available_slots=available_slots,
                weights=weights,
                ml_duration_minutes=ml_duration_minutes,
                ml_risk_prob=ml_risk_prob,
            )
            candidates.append(candidate_resp)

        # Rank descending by composite score
        candidates.sort(key=lambda c: c.composite_score, reverse=True)

        return MatchCandidatesResponse(
            work_order_id=work_order.id,
            target_date=target_date_str,
            total_eligible=len(candidates),
            candidates=candidates[: request.max_candidates],
        )

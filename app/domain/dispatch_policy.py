from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from app.schemas.dispatch import CandidateScoreBreakdown, TechnicianCandidateResponse
from app.schemas.work_order import WorkOrderPriority, WorkOrderResponse


@dataclass
class DispatchWeights:
    distance: float = 0.40
    workload: float = 0.30
    urgency: float = 0.20
    duration: float = 0.10

    @classmethod
    def from_dict(cls, d: dict[str, float] | None) -> "DispatchWeights":
        if not d:
            return cls()
        dist = max(0.0, d.get("distance", 0.40))
        work = max(0.0, d.get("workload", 0.30))
        urg = max(0.0, d.get("urgency", 0.20))
        dur = max(0.0, d.get("duration", 0.10))
        total = dist + work + urg + dur
        if total == 0:
            return cls()
        return cls(
            distance=dist / total,
            workload=work / total,
            urgency=urg / total,
            duration=dur / total,
        )


class DispatchPolicy:
    """
    Evaluates hard feasibility constraints and computes multi-factor ranking
    scores for technician candidate matching.
    """

    @staticmethod
    def satisfies_skills(technician_skills: list[str], required_skills: list[str]) -> bool:
        if not required_skills:
            return True
        tech_set = set(technician_skills)
        return set(required_skills).issubset(tech_set)

    @staticmethod
    def satisfies_service_area(distance_km: float, max_radius_km: float) -> bool:
        return distance_km <= max_radius_km

    @staticmethod
    def get_shift_for_day(
        shift_schedule: dict[str, Any] | None, target_day_name: str
    ) -> tuple[time, time] | None:
        """
        Check if technician has a working shift on the specified day of week (e.g. MONDAY).
        Returns (start_time, end_time) or None if off duty.
        """
        if not shift_schedule or "weekly_hours" not in shift_schedule:
            # Default standard working hours: 08:00 - 17:00
            return time(8, 0), time(17, 0)

        weekly_hours = shift_schedule.get("weekly_hours", [])
        for shift in weekly_hours:
            if shift.get("day_of_week") == target_day_name:
                start_parts = [int(p) for p in shift["start_time"].split(":")]
                end_parts = [int(p) for p in shift["end_time"].split(":")]
                return time(start_parts[0], start_parts[1]), time(end_parts[0], end_parts[1])
        return None

    @classmethod
    def score_candidate(
        cls,
        technician: dict[str, Any],
        work_order: WorkOrderResponse,
        distance_km: float,
        drive_time_minutes: int,
        active_jobs_count: int,
        available_slots: list[datetime],
        weights: DispatchWeights,
        ml_duration_minutes: float | None = None,
        ml_risk_prob: float | None = None,
    ) -> TechnicianCandidateResponse:
        max_radius = float(technician.get("max_travel_radius_km", 40.0))

        # 1. Distance score (closer = higher)
        dist_score = max(0.0, min(1.0, 1.0 - (distance_km / max(1.0, max_radius))))

        # 2. Workload score (fewer active jobs today = higher)
        max_expected_daily_jobs = 5.0
        workload_score = max(0.0, min(1.0, 1.0 - (active_jobs_count / max_expected_daily_jobs)))

        # 3. Urgency score (if EMERGENCY or HIGH, proximity & immediate availability matters more)
        is_urgent = work_order.priority in (WorkOrderPriority.EMERGENCY, WorkOrderPriority.HIGH)
        if is_urgent:
            urgency_score = dist_score * 0.8 + (1.0 if available_slots else 0.0) * 0.2
        else:
            urgency_score = 0.5 + 0.5 * workload_score

        # 4. Duration fit score (job fits comfortably within working window)
        effective_duration = ml_duration_minutes or work_order.estimated_duration_minutes
        duration_fit = 1.0 if effective_duration <= 120 else 0.75

        # Weighted composite utility score
        base_composite = (
            weights.distance * dist_score
            + weights.workload * workload_score
            + weights.urgency * urgency_score
            + weights.duration * duration_fit
        )

        # Minor reliability adjustment from ML risk without overriding hard constraints
        risk_adjustment = 0.0
        if ml_risk_prob is not None:
            if ml_risk_prob < 0.20:
                risk_adjustment = 0.02
            elif ml_risk_prob > 0.45:
                risk_adjustment = -0.03

        composite_score = round(max(0.0, min(1.0, base_composite + risk_adjustment)), 3)

        # Generate transparent human-readable explanation
        skills_str = ", ".join(technician.get("skills", []))
        exp_parts = [
            f"{technician['name']} is {distance_km:.1f} km away (~{drive_time_minutes} min drive).",
            f"Holds certified skills: [{skills_str}].",
            f"Current daily workload: {active_jobs_count} job(s).",
        ]
        if ml_duration_minutes:
            exp_parts.append(f"ML predicted job duration: {ml_duration_minutes:.0f}m.")
        if ml_risk_prob is not None:
            risk_label = (
                "LOW" if ml_risk_prob < 0.20 else ("MEDIUM" if ml_risk_prob < 0.45 else "HIGH")
            )
            exp_parts.append(f"ML missed-appointment risk: {risk_label} ({ml_risk_prob:.0%}).")
        if is_urgent:
            exp_parts.append(f"Ranked high for {work_order.priority.value} urgency dispatch.")
        if available_slots:
            exp_parts.append(f"Has {len(available_slots)} available slot(s) on target date.")
        else:
            exp_parts.append("Has tight schedule availability.")

        explanation = " ".join(exp_parts)

        breakdown = CandidateScoreBreakdown(
            distance_km=distance_km,
            drive_time_minutes=drive_time_minutes,
            distance_score=round(dist_score, 3),
            active_jobs_count=active_jobs_count,
            workload_score=round(workload_score, 3),
            urgency_score=round(urgency_score, 3),
            duration_fit_score=round(duration_fit, 3),
            predicted_job_duration_minutes=ml_duration_minutes,
            predicted_missed_risk=ml_risk_prob,
        )

        return TechnicianCandidateResponse(
            technician_id=str(technician["id"]),
            name=technician["name"],
            skills=technician.get("skills", []),
            composite_score=composite_score,
            score_breakdown=breakdown,
            explanation=explanation,
            available_start_times=available_slots,
        )

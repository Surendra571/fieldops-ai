from datetime import datetime

from pydantic import BaseModel, Field


class CandidateScoreBreakdown(BaseModel):
    distance_km: float
    drive_time_minutes: int
    distance_score: float = Field(..., ge=0.0, le=1.0)
    active_jobs_count: int
    workload_score: float = Field(..., ge=0.0, le=1.0)
    urgency_score: float = Field(..., ge=0.0, le=1.0)
    duration_fit_score: float = Field(..., ge=0.0, le=1.0)
    predicted_job_duration_minutes: float | None = None
    predicted_missed_risk: float | None = None


class TechnicianCandidateResponse(BaseModel):
    technician_id: str
    name: str
    skills: list[str]
    composite_score: float = Field(..., ge=0.0, le=1.0)
    score_breakdown: CandidateScoreBreakdown
    explanation: str
    available_start_times: list[datetime] = Field(default_factory=list)


class MatchCandidatesRequest(BaseModel):
    work_order_id: str
    target_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    max_candidates: int = Field(default=5, ge=1, le=20)
    weights: dict[str, float] | None = Field(
        None,
        description="Custom scoring weights e.g. {'distance': 0.4, 'workload': 0.3, 'urgency': 0.2, 'duration': 0.1}",
    )


class MatchCandidatesResponse(BaseModel):
    work_order_id: str
    target_date: str
    total_eligible: int
    candidates: list[TechnicianCandidateResponse]

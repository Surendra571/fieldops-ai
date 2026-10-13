from typing import Any

from pydantic import BaseModel, Field


class JobDurationPredictionRequest(BaseModel):
    category: str = Field(
        ..., description="Service issue category (HVAC, PLUMBING, ELECTRICAL, APPLIANCE, ROOFING)"
    )
    equipment_type: str | None = Field(None, description="Equipment model or sub-type")
    equipment_age_years: float | None = Field(
        None, ge=0, le=50, description="Age of equipment in years"
    )
    urgency: str = Field(
        "MEDIUM", description="Job priority/urgency (ROUTINE, MEDIUM, HIGH, EMERGENCY)"
    )
    technician_experience_years: float | None = Field(
        None, ge=0, le=40, description="Years of technician experience"
    )
    technician_active_jobs_count: int = Field(
        0, ge=0, description="Number of other jobs assigned to technician today"
    )
    historical_jobs_completed: int = Field(
        0, ge=0, description="Total completed jobs by customer or technician"
    )
    distance_km: float | None = Field(None, ge=0, description="Travel distance in kilometers")
    estimated_duration_minutes: int | None = Field(
        None, ge=15, le=480, description="Initial heuristic estimate"
    )


class JobDurationPredictionResponse(BaseModel):
    predicted_duration_minutes: float
    confidence_lower_minutes: float
    confidence_upper_minutes: float
    baseline_duration_minutes: float
    model_version: str
    used_fallback: bool
    latency_ms: float


class MissedAppointmentRiskRequest(BaseModel):
    category: str = Field("HVAC", description="Service category")
    customer_total_jobs: int = Field(1, ge=0, description="Prior jobs requested by customer")
    customer_no_show_history_count: int = Field(
        0, ge=0, description="Customer past no-shows or last-minute cancellations"
    )
    scheduled_hour_of_day: int = Field(
        10, ge=0, le=23, description="Appointment hour of day (0-23)"
    )
    scheduled_day_of_week: int = Field(
        1, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)"
    )
    travel_distance_km: float = Field(
        10.0, ge=0, description="Estimated technician travel distance in km"
    )
    technician_experience_years: float | None = Field(
        3.0, ge=0, description="Technician experience in years"
    )
    urgency: str = Field("MEDIUM", description="Urgency level")
    lead_time_hours: float = Field(
        24.0, ge=0, description="Hours between booking creation and appointment scheduled start"
    )


class MissedAppointmentRiskResponse(BaseModel):
    risk_probability: float
    risk_tier: str  # "LOW", "MEDIUM", "HIGH"
    baseline_probability: float
    contributing_factors: list[str]
    model_version: str
    used_fallback: bool
    latency_ms: float


class ModelEvaluationSummary(BaseModel):
    model_name: str
    version: str
    created_at: str
    target: str
    features: list[str]
    model_type: str
    metrics: dict[str, float]
    baseline_metrics: dict[str, float]
    dataset_summary: dict[str, Any]
    assumptions_and_limitations: list[str]


class DriftMonitoringResponse(BaseModel):
    monitoring_window_samples: int
    feature_means: dict[str, float]
    baseline_feature_means: dict[str, float]
    drift_detected: bool
    drift_alerts: list[str]

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_roles
from app.ml.schemas import (
    DriftMonitoringResponse,
    JobDurationPredictionRequest,
    JobDurationPredictionResponse,
    MissedAppointmentRiskRequest,
    MissedAppointmentRiskResponse,
)
from app.ml.service import MLPredictionService, get_ml_service
from app.ml.trainer import train_and_save_models
from app.schemas.user import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["Machine Learning Inference & Monitoring"])


@router.post(
    "/predict/duration",
    response_model=JobDurationPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict job duration using Model A regression pipeline",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
def predict_job_duration(
    request: JobDurationPredictionRequest,
    service: MLPredictionService = Depends(get_ml_service),
) -> JobDurationPredictionResponse:
    """
    Predict expected job duration (in minutes) from pre-job features (category, equipment, technician experience, workload).
    Includes 95% confidence intervals and historical-average baseline comparison.
    """
    return service.predict_job_duration(request)


@router.post(
    "/predict/risk",
    response_model=MissedAppointmentRiskResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict missed-appointment risk using Model B classifier",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
def predict_missed_appointment_risk(
    request: MissedAppointmentRiskRequest,
    service: MLPredictionService = Depends(get_ml_service),
) -> MissedAppointmentRiskResponse:
    """
    Predict missed-appointment or late-arrival risk probability using pre-appointment features.
    Categorizes into LOW, MEDIUM, or HIGH risk tiers with transparent contributing factors.
    """
    return service.predict_missed_appointment_risk(request)


@router.get(
    "/models/metadata",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve versioned model metadata and evaluation metrics",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
def get_model_metadata(
    service: MLPredictionService = Depends(get_ml_service),
) -> dict[str, Any]:
    """
    Returns versioned model metadata, training dataset parameters, and performance benchmarks vs baselines.
    """
    return service.get_metadata()


@router.get(
    "/monitoring/drift",
    response_model=DriftMonitoringResponse,
    status_code=status.HTTP_200_OK,
    summary="Monitor feature distribution data drift",
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.DISPATCHER, UserRole.TECHNICIAN))],
)
def monitor_data_drift(
    threshold_pct: float = Query(35.0, ge=5.0, le=100.0, description="Drift threshold percentage"),
    service: MLPredictionService = Depends(get_ml_service),
) -> DriftMonitoringResponse:
    """
    Compares recent prediction requests against training feature distributions and flags significant drift.
    """
    return service.check_data_drift(threshold_pct=threshold_pct)


@router.post(
    "/train",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Trigger reproducible model training run (Admin only)",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
def trigger_training(
    n_samples: int = Query(3000, ge=500, le=20000),
    seed: int = Query(42),
    service: MLPredictionService = Depends(get_ml_service),
) -> dict[str, Any]:
    """
    Retrains both Model A and Model B, saves artifacts, and reloads active prediction service.
    """
    result = train_and_save_models(n_samples=n_samples, seed=seed)
    service.load_artifacts()
    return result

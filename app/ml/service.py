import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.ml.data_generator import CATEGORY_BASE_DURATION
from app.ml.duration_model import extract_duration_matrix
from app.ml.risk_model import extract_risk_matrix
from app.ml.schemas import (
    DriftMonitoringResponse,
    JobDurationPredictionRequest,
    JobDurationPredictionResponse,
    MissedAppointmentRiskRequest,
    MissedAppointmentRiskResponse,
)

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


class MLPredictionService:
    """
    Production-minded ML prediction service providing duration regression,
    missed-appointment risk classification, fallbacks, and data drift monitoring.
    """

    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self._duration_artifact: dict[str, Any] | None = None
        self._risk_artifact: dict[str, Any] | None = None
        self._metadata: dict[str, Any] | None = None

        # In-memory sliding window for online data drift monitoring (last 500 samples)
        self._monitoring_window: deque[dict[str, Any]] = deque(maxlen=500)

        # Attempt initial load
        self.load_artifacts()

    def load_artifacts(self) -> None:
        """Loads serialized model pipelines and version metadata from disk."""
        dur_path = self.artifacts_dir / "duration_model_v1.joblib"
        risk_path = self.artifacts_dir / "risk_model_v1.joblib"
        meta_path = self.artifacts_dir / "model_metadata.json"

        if dur_path.exists():
            try:
                self._duration_artifact = joblib.load(dur_path)
                logger.info("Successfully loaded duration model artifact.")
            except Exception as e:
                logger.error("Failed to load duration model: %s", e)
                self._duration_artifact = None

        if risk_path.exists():
            try:
                self._risk_artifact = joblib.load(risk_path)
                logger.info("Successfully loaded risk model artifact.")
            except Exception as e:
                logger.error("Failed to load risk model: %s", e)
                self._risk_artifact = None

        if meta_path.exists():
            try:
                with open(meta_path, encoding="utf-8") as f:
                    self._metadata = json.load(f)
            except Exception as e:
                logger.error("Failed to load model metadata: %s", e)
                self._metadata = None

    def get_metadata(self) -> dict[str, Any]:
        """Returns loaded model metadata or fallback description."""
        if self._metadata:
            return self._metadata
        return {
            "version": "1.0.0-fallback",
            "status": "unloaded_or_fallback",
            "models": {
                "duration_model": {
                    "model_type": "HeuristicFallback",
                    "target": "actual_duration_minutes",
                },
                "risk_model": {"model_type": "HeuristicFallback", "target": "is_missed_or_late"},
            },
        }

    # -------------------------------------------------------------
    # Model A: Job Duration Regression
    # -------------------------------------------------------------
    def predict_job_duration(
        self, request: JobDurationPredictionRequest
    ) -> JobDurationPredictionResponse:
        t0 = time.perf_counter()
        req_dict = request.model_dump()
        self._record_sample_for_drift(req_dict)

        cat = request.category.upper()
        base_dur = CATEGORY_BASE_DURATION.get(cat, 60.0)
        version = "1.0.0"

        if self._duration_artifact is not None:
            try:
                pipeline = self._duration_artifact["pipeline"]
                version = self._duration_artifact.get("version", "1.0.0")

                # Extract 2D matrix
                X, _ = extract_duration_matrix([req_dict])
                predicted_val = float(pipeline.predict(X)[0])
                predicted_val = max(15.0, round(predicted_val, 1))

                # Estimated standard error based on test RMSE (~8.7 minutes)
                rmse = 8.7
                lower = max(15.0, round(predicted_val - 1.96 * rmse, 1))
                upper = round(predicted_val + 1.96 * rmse, 1)

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "Duration prediction: cat=%s, pred=%.1f min, latency=%.2f ms",
                    cat,
                    predicted_val,
                    elapsed_ms,
                )

                return JobDurationPredictionResponse(
                    predicted_duration_minutes=predicted_val,
                    confidence_lower_minutes=lower,
                    confidence_upper_minutes=upper,
                    baseline_duration_minutes=base_dur,
                    model_version=version,
                    used_fallback=False,
                    latency_ms=round(elapsed_ms, 2),
                )
            except Exception as e:
                logger.warning("Duration pipeline inference failed, using fallback: %s", e)

        # Deterministic Heuristic Fallback
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        predicted_val = float(request.estimated_duration_minutes or base_dur)
        if request.urgency.upper() == "EMERGENCY":
            predicted_val += 15.0

        return JobDurationPredictionResponse(
            predicted_duration_minutes=predicted_val,
            confidence_lower_minutes=max(15.0, predicted_val - 20.0),
            confidence_upper_minutes=predicted_val + 20.0,
            baseline_duration_minutes=base_dur,
            model_version="1.0.0-fallback",
            used_fallback=True,
            latency_ms=round(elapsed_ms, 2),
        )

    # -------------------------------------------------------------
    # Model B: Missed-Appointment Risk Classification
    # -------------------------------------------------------------
    def predict_missed_appointment_risk(
        self, request: MissedAppointmentRiskRequest
    ) -> MissedAppointmentRiskResponse:
        t0 = time.perf_counter()
        req_dict = request.model_dump()
        self._record_sample_for_drift(req_dict)

        version = "1.0.0"
        baseline_prob = 0.13

        contributing_factors: list[str] = []
        if request.customer_no_show_history_count > 0:
            contributing_factors.append(
                f"Customer has {request.customer_no_show_history_count} previous missed appointments or late cancellations"
            )
        if request.lead_time_hours > 120.0:
            contributing_factors.append(
                f"Booking lead time of {request.lead_time_hours:.0f}h (> 5 days) increases customer forgetfulness risk"
            )
        if (16 <= request.scheduled_hour_of_day <= 18) and request.travel_distance_km > 20.0:
            contributing_factors.append(
                f"Afternoon peak traffic window with {request.travel_distance_km:.1f} km transit increases technician late-arrival risk"
            )
        if (request.technician_experience_years or 3.0) < 2.0:
            contributing_factors.append("Junior technician on duty")

        if self._risk_artifact is not None:
            try:
                pipeline = self._risk_artifact["pipeline"]
                version = self._risk_artifact.get("version", "1.0.0")

                X, _ = extract_risk_matrix([req_dict])
                prob = float(pipeline.predict_proba(X)[0][1])
                prob = round(float(np.clip(prob, 0.01, 0.99)), 3)

                # Determine Risk Tier
                if prob < 0.20:
                    tier = "LOW"
                elif prob < 0.45:
                    tier = "MEDIUM"
                else:
                    tier = "HIGH"

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "Risk prediction: prob=%.3f, tier=%s, latency=%.2f ms",
                    prob,
                    tier,
                    elapsed_ms,
                )

                return MissedAppointmentRiskResponse(
                    risk_probability=prob,
                    risk_tier=tier,
                    baseline_probability=baseline_prob,
                    contributing_factors=contributing_factors,
                    model_version=version,
                    used_fallback=False,
                    latency_ms=round(elapsed_ms, 2),
                )
            except Exception as e:
                logger.warning("Risk pipeline inference failed, using fallback: %s", e)

        # Heuristic Fallback
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        prob = 0.12
        if request.customer_no_show_history_count > 0:
            prob += 0.30
        if request.lead_time_hours > 120.0:
            prob += 0.15
        if request.travel_distance_km > 30.0:
            prob += 0.10
        prob = round(float(np.clip(prob, 0.05, 0.95)), 3)
        tier = "HIGH" if prob >= 0.45 else ("MEDIUM" if prob >= 0.20 else "LOW")

        return MissedAppointmentRiskResponse(
            risk_probability=prob,
            risk_tier=tier,
            baseline_probability=baseline_prob,
            contributing_factors=contributing_factors,
            model_version="1.0.0-fallback",
            used_fallback=True,
            latency_ms=round(elapsed_ms, 2),
        )

    # -------------------------------------------------------------
    # Online Data Drift Monitoring
    # -------------------------------------------------------------
    def _record_sample_for_drift(self, sample: dict[str, Any]) -> None:
        numeric_sample: dict[str, float] = {}
        for k in [
            "equipment_age_years",
            "technician_experience_years",
            "distance_km",
            "travel_distance_km",
            "lead_time_hours",
        ]:
            if k in sample and sample[k] is not None:
                try:
                    numeric_sample[k] = float(sample[k])
                except (ValueError, TypeError):
                    pass
        if numeric_sample:
            self._monitoring_window.append(numeric_sample)

    def check_data_drift(self, threshold_pct: float = 35.0) -> DriftMonitoringResponse:
        """
        Compares sliding window feature averages against training baseline feature averages.
        Alerts when feature distribution shifts by more than threshold_pct.
        """
        baseline_means = (self._metadata or {}).get(
            "baseline_feature_means",
            {
                "equipment_age_years": 8.0,
                "technician_experience_years": 5.5,
                "distance_km": 12.0,
                "travel_distance_km": 12.0,
                "lead_time_hours": 48.0,
            },
        )

        if not self._monitoring_window:
            return DriftMonitoringResponse(
                monitoring_window_samples=0,
                feature_means={},
                baseline_feature_means=baseline_means,
                drift_detected=False,
                drift_alerts=[],
            )

        window_means: dict[str, float] = {}
        drift_alerts: list[str] = []

        all_keys = set(baseline_means.keys())
        for k in all_keys:
            vals = [s[k] for s in self._monitoring_window if k in s]
            if vals:
                curr_mean = float(np.mean(vals))
                window_means[k] = round(curr_mean, 2)
                base_val = baseline_means.get(k)
                if base_val and base_val > 0:
                    pct_change = abs(curr_mean - base_val) / base_val * 100.0
                    if pct_change >= threshold_pct:
                        drift_alerts.append(
                            f"Drift alert on '{k}': current mean {curr_mean:.2f} shifted by {pct_change:.1f}% from baseline {base_val:.2f}"
                        )

        return DriftMonitoringResponse(
            monitoring_window_samples=len(self._monitoring_window),
            feature_means=window_means,
            baseline_feature_means=baseline_means,
            drift_detected=len(drift_alerts) > 0,
            drift_alerts=drift_alerts,
        )


_ml_service_instance: MLPredictionService | None = None


def get_ml_service() -> MLPredictionService:
    global _ml_service_instance
    if _ml_service_instance is None:
        _ml_service_instance = MLPredictionService()
    return _ml_service_instance

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath("."))

import joblib
import numpy as np

from app.ml.data_generator import (
    DEFAULT_RANDOM_SEED,
    generate_synthetic_field_service_dataset,
    split_dataset_temporally,
)
from app.ml.duration_model import (
    HistoricalCategoryAverageBaseline,
    build_duration_pipeline,
    evaluate_regression_metrics,
    extract_duration_matrix,
)
from app.ml.risk_model import (
    PriorFrequencyRiskBaseline,
    build_risk_pipeline,
    evaluate_classification_metrics,
    extract_risk_matrix,
)

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def train_and_save_models(
    n_samples: int = 3000,
    seed: int = DEFAULT_RANDOM_SEED,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Executes a reproducible end-to-end training, validation, and evaluation pipeline.
    Saves trained artifacts and versioned metadata to disk.
    """
    save_dir = artifacts_dir or ARTIFACTS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("                     FIELDOPS AI - PHASE 5 ML TRAINING PIPELINE                 ")
    print("================================================================================")
    print(f"Random Seed           : {seed}")
    print(f"Sample Count          : {n_samples}")
    print(f"Artifacts Destination : {save_dir}")

    # 1. Generate Dataset
    print("\n1. Generating synthetic dataset with realistic distributions...")
    dataset = generate_synthetic_field_service_dataset(n_samples=n_samples, seed=seed)

    # 2. Temporal Split
    print("2. Splitting dataset temporally (70% train, 15% validation, 15% test)...")
    train_data, val_data, test_data = split_dataset_temporally(dataset, 0.70, 0.15)
    print(
        f"   Train samples: {len(train_data)} | Val samples: {len(val_data)} | Test samples: {len(test_data)}"
    )

    # -------------------------------------------------------------
    # 3. Model A: Job Duration Regression
    # -------------------------------------------------------------
    print("\n3. Training Model A: Job Duration Regression...")
    X_train_dur, y_train_dur = extract_duration_matrix(train_data)
    X_test_dur, y_test_dur = extract_duration_matrix(test_data)

    # Baseline: Historical category mean
    duration_baseline = HistoricalCategoryAverageBaseline()
    duration_baseline.fit(train_data)
    y_pred_dur_baseline = duration_baseline.predict(test_data)
    dur_baseline_metrics = evaluate_regression_metrics(y_test_dur, y_pred_dur_baseline)

    # ML Model: HistGradientBoostingRegressor Pipeline
    duration_pipeline = build_duration_pipeline(random_state=seed)
    duration_pipeline.fit(X_train_dur, y_train_dur)
    y_pred_dur_ml = duration_pipeline.predict(X_test_dur)
    dur_ml_metrics = evaluate_regression_metrics(y_test_dur, y_pred_dur_ml)

    print("   [Model A Baseline (Historical Avg)] ->", dur_baseline_metrics)
    print("   [Model A ML Pipeline (GBDT)]         ->", dur_ml_metrics)

    # Compute baseline feature distributions for drift monitoring
    feature_means_baseline = {
        "equipment_age_years": float(
            np.nanmean(
                [
                    r.get("equipment_age_years")
                    for r in train_data
                    if r.get("equipment_age_years") is not None
                ]
            )
        ),
        "technician_experience_years": float(
            np.nanmean(
                [
                    r.get("technician_experience_years")
                    for r in train_data
                    if r.get("technician_experience_years") is not None
                ]
            )
        ),
        "distance_km": float(
            np.nanmean(
                [r.get("distance_km") for r in train_data if r.get("distance_km") is not None]
            )
        ),
        "travel_distance_km": float(
            np.nanmean(
                [
                    r.get("travel_distance_km")
                    for r in train_data
                    if r.get("travel_distance_km") is not None
                ]
            )
        ),
        "lead_time_hours": float(
            np.nanmean(
                [
                    r.get("lead_time_hours")
                    for r in train_data
                    if r.get("lead_time_hours") is not None
                ]
            )
        ),
        "actual_duration_minutes": float(np.nanmean(y_train_dur)),
    }

    # -------------------------------------------------------------
    # 4. Model B: Missed-Appointment Risk Classification
    # -------------------------------------------------------------
    print("\n4. Training Model B: Missed-Appointment Risk Classification...")
    X_train_risk, y_train_risk = extract_risk_matrix(train_data)
    X_test_risk, y_test_risk = extract_risk_matrix(test_data)

    # Baseline: Prior frequency classifier
    risk_baseline = PriorFrequencyRiskBaseline()
    risk_baseline.fit(train_data)
    y_prob_risk_baseline = risk_baseline.predict_proba(test_data)[:, 1]
    risk_baseline_metrics = evaluate_classification_metrics(
        y_test_risk, y_prob_risk_baseline, threshold=0.50
    )

    # ML Model: HistGradientBoostingClassifier Pipeline
    risk_pipeline = build_risk_pipeline(random_state=seed)
    risk_pipeline.fit(X_train_risk, y_train_risk)
    y_prob_risk_ml = risk_pipeline.predict_proba(X_test_risk)[:, 1]
    risk_ml_metrics = evaluate_classification_metrics(y_test_risk, y_prob_risk_ml, threshold=0.35)

    print("   [Model B Baseline (Marginal Prior)]  ->", risk_baseline_metrics)
    print("   [Model B ML Pipeline (GBDT)]         ->", risk_ml_metrics)

    # -------------------------------------------------------------
    # 5. Serialize Artifacts
    # -------------------------------------------------------------
    print("\n5. Serializing trained models and versioned metadata...")
    duration_model_path = save_dir / "duration_model_v1.joblib"
    risk_model_path = save_dir / "risk_model_v1.joblib"
    metadata_path = save_dir / "model_metadata.json"

    # Save models including baseline fallback objects
    joblib.dump(
        {
            "pipeline": duration_pipeline,
            "baseline": duration_baseline,
            "version": "1.0.0",
            "random_state": seed,
        },
        duration_model_path,
    )

    joblib.dump(
        {
            "pipeline": risk_pipeline,
            "baseline": risk_baseline,
            "version": "1.0.0",
            "random_state": seed,
        },
        risk_model_path,
    )

    now_iso = datetime.now(UTC).isoformat()
    metadata: dict[str, Any] = {
        "status": "loaded",
        "version": "1.0.0",
        "trained_at": now_iso,
        "random_seed": seed,
        "n_samples": n_samples,
        "split": {
            "train_samples": len(train_data),
            "val_samples": len(val_data),
            "test_samples": len(test_data),
            "method": "temporal_chronological_split",
        },
        "models": {
            "duration_model": {
                "name": "JobDurationRegressor",
                "version": "1.0.0",
                "model_type": "HistGradientBoostingRegressor",
                "metrics": dur_ml_metrics,
                "baseline_metrics": dur_baseline_metrics,
                "target": "actual_duration_minutes",
            },
            "risk_model": {
                "name": "MissedAppointmentRiskClassifier",
                "version": "1.0.0",
                "model_type": "HistGradientBoostingClassifier",
                "decision_threshold": 0.35,
                "metrics": risk_ml_metrics,
                "baseline_metrics": risk_baseline_metrics,
                "target": "is_missed_or_late",
            },
        },
        "baseline_feature_means": feature_means_baseline,
        "assumptions_and_limitations": [
            "Synthetic data generated with fixed random seeds for deterministic evaluation.",
            "Synthetic labels reflect simulated noise and domain heuristics; real-world deployment requires production data ingestion.",
            "Cold-start heuristics are provided as deterministic fallback baselines.",
            "Low-confidence ML predictions must never override hard technician constraints (skills, working hours).",
        ],
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Artifacts successfully saved to: {save_dir}")
    print("================================================================================\n")

    return metadata


if __name__ == "__main__":
    train_and_save_models()

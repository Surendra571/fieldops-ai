import tempfile
from pathlib import Path

from app.ml.data_generator import generate_synthetic_dataset, split_dataset_temporally
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
from app.ml.schemas import JobDurationPredictionRequest, MissedAppointmentRiskRequest
from app.ml.service import MLPredictionService
from app.ml.trainer import train_and_save_models


def test_synthetic_data_generator_reproducibility():
    """Verify data generator is strictly deterministic with fixed seed."""
    ds1 = generate_synthetic_dataset(num_samples=100, seed=42)
    ds2 = generate_synthetic_dataset(num_samples=100, seed=42)
    ds3 = generate_synthetic_dataset(num_samples=100, seed=99)

    assert len(ds1) == 100
    assert len(ds2) == 100
    assert ds1[0] == ds2[0]
    assert ds1[50] == ds2[50]
    # Different seed should yield different samples
    assert ds1[0]["actual_duration_minutes"] != ds3[0]["actual_duration_minutes"]

    # Verify field types and expected bounds
    row = ds1[0]
    assert "timestamp" in row
    assert "category" in row
    assert "actual_duration_minutes" in row
    assert "is_missed_or_late" in row
    assert row["actual_duration_minutes"] > 0
    assert row["is_missed_or_late"] in (0, 1)


def test_temporal_split_integrity():
    """Ensure temporal splitting strictly orders data chronologically with no future leakage."""
    dataset = generate_synthetic_dataset(num_samples=200, seed=42)
    train_data, val_data, test_data = split_dataset_temporally(
        dataset, train_ratio=0.70, val_ratio=0.15
    )

    assert len(train_data) == 140
    assert len(val_data) == 30
    assert len(test_data) == 30

    train_max_ts = max(r["timestamp"] for r in train_data)
    val_min_ts = min(r["timestamp"] for r in val_data)
    val_max_ts = max(r["timestamp"] for r in val_data)
    test_min_ts = min(r["timestamp"] for r in test_data)

    assert train_max_ts <= val_min_ts, "Train set overlaps with validation set chronologically!"
    assert val_max_ts <= test_min_ts, "Validation set overlaps with test set chronologically!"


def test_duration_model_training_and_baseline_comparison():
    """Verify Model A training, preprocessing fit on train only, and outperforming baseline."""
    dataset = generate_synthetic_dataset(num_samples=300, seed=42)
    train_data, val_data, test_data = split_dataset_temporally(
        dataset, train_ratio=0.70, val_ratio=0.15
    )

    base_model = HistoricalCategoryAverageBaseline().fit(train_data)
    pipeline = build_duration_pipeline(random_state=42)

    X_train, y_train = extract_duration_matrix(train_data)
    pipeline.fit(X_train, y_train)

    X_test, y_test = extract_duration_matrix(test_data)
    ml_metrics = evaluate_regression_metrics(y_test, pipeline.predict(X_test))
    base_metrics = evaluate_regression_metrics(y_test, base_model.predict(test_data))

    assert "mae" in ml_metrics
    assert "rmse" in ml_metrics
    assert "r2" in ml_metrics
    # ML model should achieve lower MAE than simple category average baseline
    assert ml_metrics["mae"] <= base_metrics["mae"]
    assert ml_metrics["rmse"] <= base_metrics["rmse"]

    # Test inference on record with missing values
    test_record = {
        "category": "HVAC",
        "equipment_type": None,
        "equipment_age_years": None,
        "urgency": "HIGH",
        "technician_experience_years": None,
        "technician_active_jobs_count": 1,
        "historical_jobs_completed": 5,
        "distance_km": None,
        "estimated_duration_minutes": 60,
    }
    X_single, _ = extract_duration_matrix([test_record])
    pred = pipeline.predict(X_single)
    assert len(pred) == 1
    assert pred[0] > 0


def test_risk_model_training_and_calibration():
    """Verify Model B classification training, metrics reporting, and calibration."""
    dataset = generate_synthetic_dataset(num_samples=400, seed=42)
    train_data, val_data, test_data = split_dataset_temporally(
        dataset, train_ratio=0.70, val_ratio=0.15
    )

    base_model = PriorFrequencyRiskBaseline().fit(train_data)
    pipeline = build_risk_pipeline(random_state=42)

    X_train, y_train = extract_risk_matrix(train_data)
    pipeline.fit(X_train, y_train)

    X_test, y_test = extract_risk_matrix(test_data)
    ml_metrics = evaluate_classification_metrics(y_test, pipeline.predict_proba(X_test)[:, 1])
    base_metrics = evaluate_classification_metrics(y_test, base_model.predict_proba(test_data))

    assert "pr_auc" in ml_metrics
    assert "pr_auc" in base_metrics
    assert "brier_score" in ml_metrics
    assert "recall" in ml_metrics
    assert "precision" in ml_metrics
    # Probabilities must be bounded [0, 1]
    assert 0.0 <= ml_metrics["brier_score"] <= 1.0

    # Test prediction probabilities
    test_record = {
        "category": "PLUMBING",
        "customer_total_jobs": 0,
        "customer_no_show_history_count": 2,
        "scheduled_hour_of_day": 18,
        "scheduled_day_of_week": 4,
        "travel_distance_km": 35.0,
        "technician_experience_years": 1.0,
        "urgency": "HIGH",
        "lead_time_hours": 3.0,
    }
    X_single, _ = extract_risk_matrix([test_record])
    proba = pipeline.predict_proba(X_single)[0]
    assert len(proba) == 2
    assert 0.0 <= proba[1] <= 1.0


def test_trainer_end_to_end_serialization():
    """Verify trainer builds, evaluates, and serializes artifacts cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        summary = train_and_save_models(n_samples=250, seed=42, artifacts_dir=tmp_path)

        assert (tmp_path / "duration_model_v1.joblib").exists()
        assert (tmp_path / "risk_model_v1.joblib").exists()
        assert (tmp_path / "model_metadata.json").exists()
        assert "duration_model" in summary["models"]
        assert "risk_model" in summary["models"]


def test_prediction_service_deterministic_inference():
    """Verify MLPredictionService produces deterministic results and handles missing values."""
    service = MLPredictionService()
    req = JobDurationPredictionRequest(
        category="ELECTRICAL",
        urgency="ROUTINE",
        technician_experience_years=5.0,
        technician_active_jobs_count=0,
        distance_km=12.5,
        estimated_duration_minutes=45,
    )
    res1 = service.predict_job_duration(req)
    res2 = service.predict_job_duration(req)

    assert res1.predicted_duration_minutes == res2.predicted_duration_minutes
    assert res1.confidence_lower_minutes == res2.confidence_lower_minutes
    assert res1.confidence_upper_minutes == res2.confidence_upper_minutes
    assert res1.model_version == res2.model_version


def test_prediction_service_fallback_on_unloaded_model():
    """Verify fallback behavior when models are absent or fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Service initialized with empty directory has no model artifacts
        fallback_service = MLPredictionService(artifacts_dir=Path(tmpdir))

        dur_res = fallback_service.predict_job_duration(
            JobDurationPredictionRequest(category="HVAC", urgency="EMERGENCY")
        )
        assert dur_res.used_fallback is True
        assert dur_res.predicted_duration_minutes > 0

        risk_res = fallback_service.predict_missed_appointment_risk(
            MissedAppointmentRiskRequest(category="HVAC")
        )
        assert risk_res.used_fallback is True
        assert 0.0 <= risk_res.risk_probability <= 1.0

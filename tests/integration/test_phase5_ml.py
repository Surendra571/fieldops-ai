from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

# ============================================================================
# 1. MODEL A: DURATION REGRESSION ENDPOINT
# ============================================================================


async def test_duration_prediction_endpoint(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "category": "HVAC",
        "equipment_type": "Carrier 3-Ton Heat Pump",
        "equipment_age_years": 8.5,
        "urgency": "HIGH",
        "technician_experience_years": 4.0,
        "technician_active_jobs_count": 2,
        "historical_jobs_completed": 15,
        "distance_km": 14.2,
        "estimated_duration_minutes": 90,
    }

    resp = await async_client.post("/api/v1/ml/predict/duration", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "predicted_duration_minutes" in data
    assert "confidence_lower_minutes" in data
    assert "confidence_upper_minutes" in data
    assert data["predicted_duration_minutes"] > 0
    assert data["confidence_lower_minutes"] <= data["predicted_duration_minutes"]
    assert data["confidence_upper_minutes"] >= data["predicted_duration_minutes"]
    assert data["model_version"] == "1.0.0"
    assert data["used_fallback"] is False
    assert data["latency_ms"] >= 0


# ============================================================================
# 2. MODEL B: MISSED-APPOINTMENT RISK ENDPOINT
# ============================================================================


async def test_risk_prediction_endpoint(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "category": "PLUMBING",
        "customer_total_jobs": 2,
        "customer_no_show_history_count": 1,
        "scheduled_hour_of_day": 17,
        "scheduled_day_of_week": 4,  # Friday late afternoon
        "travel_distance_km": 28.5,
        "technician_experience_years": 1.5,
        "urgency": "ROUTINE",
        "lead_time_hours": 4.0,
    }

    resp = await async_client.post("/api/v1/ml/predict/risk", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "risk_probability" in data
    assert 0.0 <= data["risk_probability"] <= 1.0
    assert data["risk_tier"] in ("LOW", "MEDIUM", "HIGH")
    assert "contributing_factors" in data
    assert isinstance(data["contributing_factors"], list)
    assert data["model_version"] == "1.0.0"
    assert data["used_fallback"] is False


# ============================================================================
# 3. INPUT VALIDATION & MALFORMED INPUTS
# ============================================================================


async def test_ml_input_validation_and_malformed_inputs(
    async_client: AsyncClient, admin_token: str
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Malformed duration request: negative equipment age
    bad_dur = {
        "category": "HVAC",
        "equipment_age_years": -5.0,
    }
    dur_resp = await async_client.post("/api/v1/ml/predict/duration", json=bad_dur, headers=headers)
    assert dur_resp.status_code == 422

    # Malformed risk request: invalid scheduled_hour_of_day > 23
    bad_risk = {
        "category": "HVAC",
        "scheduled_hour_of_day": 28,
    }
    risk_resp = await async_client.post("/api/v1/ml/predict/risk", json=bad_risk, headers=headers)
    assert risk_resp.status_code == 422


# ============================================================================
# 4. VERSIONED MODEL METADATA ENDPOINT
# ============================================================================


async def test_model_metadata_endpoint(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = await async_client.get("/api/v1/ml/models/metadata", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "loaded"
    models = data["models"]
    assert "duration_model" in models
    assert "risk_model" in models

    dur_meta = models["duration_model"]
    assert dur_meta["model_type"] == "HistGradientBoostingRegressor"
    assert dur_meta["metrics"]["mae"] > 0
    assert dur_meta["metrics"]["rmse"] > 0
    assert dur_meta["metrics"]["r2"] > 0
    assert dur_meta["metrics"]["mae"] < dur_meta["baseline_metrics"]["mae"]

    risk_meta = models["risk_model"]
    assert risk_meta["model_type"] == "HistGradientBoostingClassifier"
    assert "pr_auc" in risk_meta["metrics"]
    assert "brier_score" in risk_meta["metrics"]
    assert risk_meta["metrics"]["pr_auc"] > risk_meta["baseline_metrics"]["pr_auc"]


# ============================================================================
# 5. DATA DRIFT MONITORING
# ============================================================================


async def test_data_drift_monitoring_endpoint(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Query initial monitoring state
    resp = await async_client.get("/api/v1/ml/monitoring/drift", headers=headers)
    assert resp.status_code == 200
    initial_data = resp.json()
    assert "monitoring_window_samples" in initial_data
    assert "feature_means" in initial_data
    assert "baseline_feature_means" in initial_data
    assert "drift_detected" in initial_data

    # Send a few prediction requests to verify window sample tracking
    for _ in range(3):
        await async_client.post(
            "/api/v1/ml/predict/duration",
            json={"category": "ROOFING", "distance_km": 15.0, "urgency": "MEDIUM"},
            headers=headers,
        )

    updated_resp = await async_client.get("/api/v1/ml/monitoring/drift", headers=headers)
    assert updated_resp.status_code == 200
    updated_data = updated_resp.json()
    assert (
        updated_data["monitoring_window_samples"] >= initial_data["monitoring_window_samples"] + 3
    )


# ============================================================================
# 6. DISPATCH RANKING INTEGRATION WITH ML
# ============================================================================


async def test_dispatch_ranking_incorporates_ml_predictions(
    async_client: AsyncClient,
    admin_token: str,
    sample_customer: dict,
    sample_technician: dict,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create work order
    wo_resp = await async_client.post(
        "/api/v1/work-orders",
        json={
            "customer_id": sample_customer["id"],
            "category": "HVAC",
            "priority": "HIGH",
            "required_skills": ["HVAC_EPA_CERTIFIED"],
            "description": "Commercial refrigeration condenser freezing up.",
            "service_address": sample_customer["service_addresses"][0],
            "estimated_duration_minutes": 105,
        },
        headers=headers,
    )
    assert wo_resp.status_code == 201
    wo_id = wo_resp.json()["id"]

    # Match candidates
    target_date = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    match_resp = await async_client.post(
        "/api/v1/dispatch/match-candidates",
        json={"work_order_id": wo_id, "target_date": target_date},
        headers=headers,
    )
    assert match_resp.status_code == 200
    res = match_resp.json()
    assert res["total_eligible"] >= 1
    top_cand = res["candidates"][0]

    # Verify score bounds and transparent explanation containing ML insights
    assert 0.0 <= top_cand["composite_score"] <= 1.0
    exp_text = top_cand["explanation"]
    assert "ML predicted job duration" in exp_text
    assert "ML missed-appointment risk" in exp_text


# ============================================================================
# 7. TRAINING ENDPOINT PERMISSIONS AND EXECUTION
# ============================================================================


async def test_admin_retrain_endpoint(
    async_client: AsyncClient, admin_token: str, customer_token: str
):
    # Customer should be forbidden from triggering model retraining
    cust_resp = await async_client.post(
        "/api/v1/ml/train?n_samples=500&seed=99",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert cust_resp.status_code == 403

    # Admin is authorized to retrain
    admin_resp = await async_client.post(
        "/api/v1/ml/train?n_samples=500&seed=99",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 200
    train_data = admin_resp.json()
    assert train_data.get("status") in ("loaded", "trained")
    assert "models" in train_data
    assert "duration_model" in train_data["models"]
    assert "risk_model" in train_data["models"]

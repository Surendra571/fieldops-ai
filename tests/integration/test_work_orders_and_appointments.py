from datetime import UTC, datetime, timedelta

from httpx import AsyncClient


async def test_customer_lifecycle(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    customer_payload = {
        "full_name": "Arthur Pendelton",
        "phone": "+14045550299",
        "email": "arthur@example.com",
        "preferred_channel": "SMS",
        "service_addresses": [
            {
                "street": "742 Evergreen Terrace",
                "city": "Atlanta",
                "state": "GA",
                "postal_code": "30306",
                "is_primary": True,
            }
        ],
    }

    # Create customer
    create_resp = await async_client.post(
        "/api/v1/customers", json=customer_payload, headers=headers
    )
    assert create_resp.status_code == 201
    cust_data = create_resp.json()
    assert cust_data["full_name"] == "Arthur Pendelton"
    cust_id = cust_data["id"]

    # Search customer
    search_resp = await async_client.get("/api/v1/customers?search=Arthur", headers=headers)
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] >= 1
    assert search_resp.json()["items"][0]["id"] == cust_id


async def test_technician_lifecycle_and_location(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    tech_payload = {
        "name": "Samantha Cruz",
        "email": "samantha.cruz@fieldops.ai",
        "phone": "+14045550188",
        "status": "ACTIVE",
        "skills": ["MASTER_PLUMBER"],
    }
    create_resp = await async_client.post("/api/v1/technicians", json=tech_payload, headers=headers)
    assert create_resp.status_code == 201
    tech_id = create_resp.json()["id"]

    # Update location telemetry
    loc_payload = {
        "coordinates": [-84.3850, 33.7550],
        "speed_kph": 45.0,
        "heading": 180.0,
    }
    loc_resp = await async_client.post(
        f"/api/v1/technicians/{tech_id}/location", json=loc_payload, headers=headers
    )
    assert loc_resp.status_code == 200
    assert loc_resp.json()["current_location"]["coordinates"] == [-84.3850, 33.7550]


async def test_work_order_idempotency_and_state_transitions(
    async_client: AsyncClient, admin_token: str, sample_customer: dict
):
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Idempotency-Key": "idemp-wo-test-key-100",
    }

    wo_payload = {
        "customer_id": sample_customer["id"],
        "category": "HVAC",
        "priority": "HIGH",
        "description": "AC compressor humming but fan not turning.",
        "service_address": sample_customer["service_addresses"][0],
        "estimated_duration_minutes": 90,
    }

    # 1. First submission creates work order
    resp1 = await async_client.post("/api/v1/work-orders", json=wo_payload, headers=headers)
    assert resp1.status_code == 201
    wo1 = resp1.json()
    assert wo1["status"] == "SUBMITTED"
    wo_id = wo1["id"]

    # 2. Resubmission with identical Idempotency-Key returns existing work order
    resp2 = await async_client.post("/api/v1/work-orders", json=wo_payload, headers=headers)
    assert resp2.status_code == 201
    wo2 = resp2.json()
    assert wo2["id"] == wo_id
    assert wo2["work_order_number"] == wo1["work_order_number"]

    # 3. Transition to TRIAGED
    trans_resp1 = await async_client.patch(
        f"/api/v1/work-orders/{wo_id}/status",
        json={"new_status": "TRIAGED", "reason": "Diagnosed as faulty capacitor"},
        headers=headers,
    )
    assert trans_resp1.status_code == 200
    assert trans_resp1.json()["status"] == "TRIAGED"
    assert len(trans_resp1.json()["audit_trail"]) == 2

    # 4. Attempt illegal jump from TRIAGED directly to COMPLETED -> 400 Bad Request
    illegal_resp = await async_client.patch(
        f"/api/v1/work-orders/{wo_id}/status",
        json={"new_status": "COMPLETED"},
        headers=headers,
    )
    assert illegal_resp.status_code == 400
    assert illegal_resp.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


async def test_appointment_conflict_prevention(
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
            "priority": "MEDIUM",
            "description": "Annual seasonal inspection",
            "service_address": sample_customer["service_addresses"][0],
        },
        headers=headers,
    )
    wo_id = wo_resp.json()["id"]

    # Schedule first appointment: tomorrow 10:00 to 11:30
    now = datetime.now(UTC)
    slot1_start = now + timedelta(days=1, hours=10)
    slot1_end = slot1_start + timedelta(hours=1.5)

    appt1_resp = await async_client.post(
        "/api/v1/appointments",
        json={
            "work_order_id": wo_id,
            "technician_id": sample_technician["id"],
            "customer_id": sample_customer["id"],
            "scheduled_start": slot1_start.isoformat(),
            "scheduled_end": slot1_end.isoformat(),
        },
        headers=headers,
    )
    assert appt1_resp.status_code == 201
    appt1 = appt1_resp.json()
    assert appt1["status"] == "CONFIRMED"

    # Create second work order
    wo2_resp = await async_client.post(
        "/api/v1/work-orders",
        json={
            "customer_id": sample_customer["id"],
            "category": "HVAC",
            "priority": "HIGH",
            "description": "Urgent filter replacement",
            "service_address": sample_customer["service_addresses"][0],
        },
        headers=headers,
    )
    wo2_id = wo2_resp.json()["id"]

    # Attempt to schedule overlapping appointment: starts 30 mins into slot1 (10:30 to 12:00)
    overlapping_start = slot1_start + timedelta(minutes=30)
    overlapping_end = overlapping_start + timedelta(hours=1.5)

    conflict_resp = await async_client.post(
        "/api/v1/appointments",
        json={
            "work_order_id": wo2_id,
            "technician_id": sample_technician["id"],
            "customer_id": sample_customer["id"],
            "scheduled_start": overlapping_start.isoformat(),
            "scheduled_end": overlapping_end.isoformat(),
        },
        headers=headers,
    )

    # Must be rejected with 409 Conflict
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error"]["code"] == "CONFLICT"
    assert "conflicts" in conflict_resp.json()["error"]["message"]

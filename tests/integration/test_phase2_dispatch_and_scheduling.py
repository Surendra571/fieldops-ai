import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient

# ============================================================================
# 1. IDEMPOTENCY: RETRIES & PAYLOAD MISMATCH
# ============================================================================


async def test_idempotency_retry_returns_original_and_mismatch_fails(
    async_client: AsyncClient, admin_token: str, sample_customer: dict
):
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Idempotency-Key": "test-idemp-work-order-phase2-001",
    }

    base_payload = {
        "customer_id": sample_customer["id"],
        "category": "PLUMBING",
        "priority": "HIGH",
        "description": "Kitchen sink pipe burst and flooding under counter.",
        "service_address": sample_customer["service_addresses"][0],
        "estimated_duration_minutes": 60,
    }

    # 1. First submission -> creates work order
    resp1 = await async_client.post("/api/v1/work-orders", json=base_payload, headers=headers)
    assert resp1.status_code == 201
    wo1 = resp1.json()
    assert wo1["status"] == "SUBMITTED"

    # 2. Legitimate retry with identical payload -> returns cached original without duplicating
    resp2 = await async_client.post("/api/v1/work-orders", json=base_payload, headers=headers)
    assert resp2.status_code == 201
    wo2 = resp2.json()
    assert wo2["id"] == wo1["id"]
    assert wo2["work_order_number"] == wo1["work_order_number"]

    # 3. Payload mismatch with same key -> rejected with 422 IDEMPOTENCY_PAYLOAD_MISMATCH
    mismatched_payload = dict(base_payload)
    mismatched_payload["description"] = "Completely different issue on same idempotency key."
    mismatch_resp = await async_client.post(
        "/api/v1/work-orders", json=mismatched_payload, headers=headers
    )
    assert mismatch_resp.status_code == 422
    assert mismatch_resp.json()["error"]["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"


# ============================================================================
# 2. TECHNICIAN DISPATCH & TRANSPARENT EXPLANATION
# ============================================================================


async def test_dispatch_candidate_matching_and_explanation(
    async_client: AsyncClient,
    admin_token: str,
    sample_customer: dict,
    sample_technician: dict,
    test_db,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create a second technician who does NOT have HVAC certification
    now = datetime.now(UTC)
    unqualified_tech = {
        "name": "Plumber Bob",
        "email": "bob@test.com",
        "phone": "+14045550999",
        "status": "ACTIVE",
        "skills": ["ROOFING_SPECIALIST"],  # missing HVAC_EPA_CERTIFIED
        "home_base": {"type": "Point", "coordinates": [-84.3880, 33.7490]},
        "shift_schedule": {
            "timezone": "America/New_York",
            "weekly_hours": [
                {"day_of_week": "MONDAY", "start_time": "08:00", "end_time": "17:00"},
            ],
        },
        "created_at": now,
        "updated_at": now,
    }
    await test_db["technicians"].insert_one(unqualified_tech)

    # Create work order requiring HVAC_EPA_CERTIFIED
    wo_resp = await async_client.post(
        "/api/v1/work-orders",
        json={
            "customer_id": sample_customer["id"],
            "category": "HVAC",
            "priority": "HIGH",
            "required_skills": ["HVAC_EPA_CERTIFIED"],
            "description": "AC blower motor non-responsive in heatwave.",
            "service_address": sample_customer["service_addresses"][0],
            "estimated_duration_minutes": 90,
        },
        headers=headers,
    )
    assert wo_resp.status_code == 201
    wo_id = wo_resp.json()["id"]

    # Request candidate matching
    target_date = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
    match_resp = await async_client.post(
        "/api/v1/dispatch/match-candidates",
        json={"work_order_id": wo_id, "target_date": target_date},
        headers=headers,
    )
    assert match_resp.status_code == 200
    match_data = match_resp.json()

    # Bob must be filtered out; sample_technician must be matched
    candidate_ids = [c["technician_id"] for c in match_data["candidates"]]
    assert sample_technician["id"] in candidate_ids
    assert len(match_data["candidates"]) == 1

    matched = match_data["candidates"][0]
    assert matched["composite_score"] > 0.0
    assert "explanation" in matched
    assert "score_breakdown" in matched
    assert matched["score_breakdown"]["distance_km"] >= 0.0
    assert "Marcus Brody" in matched["explanation"]


# ============================================================================
# 3. APPOINTMENT SCHEDULING: SLOTS, HOLD, CONFIRMATION GATE
# ============================================================================


async def test_appointment_slots_hold_and_confirmation_gate(
    async_client: AsyncClient,
    admin_token: str,
    sample_customer: dict,
    sample_technician: dict,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create work order
    wo_resp = await async_client.post(
        "/api/v1/work-orders",
        json={
            "customer_id": sample_customer["id"],
            "category": "HVAC",
            "priority": "HIGH",
            "description": "HVAC annual preventative maintenance check.",
            "service_address": sample_customer["service_addresses"][0],
            "estimated_duration_minutes": 60,
        },
        headers=headers,
    )
    wo_id = wo_resp.json()["id"]

    # 2. Discover available slots for tomorrow
    tomorrow = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=1)
    target_date = tomorrow.strftime("%Y-%m-%d")

    slots_resp = await async_client.post(
        "/api/v1/appointments/available-slots",
        json={
            "technician_id": sample_technician["id"],
            "target_date": target_date,
            "duration_minutes": 60,
            "buffer_minutes": 30,
            "timezone": "America/New_York",
        },
        headers=headers,
    )
    assert slots_resp.status_code == 200
    slots_data = slots_resp.json()
    assert len(slots_data["slots"]) > 0

    first_slot = slots_data["slots"][0]
    slot_start = first_slot["start_time"]
    slot_end = first_slot["end_time"]

    # 3. Place tentative 10-minute hold on first slot
    hold_resp = await async_client.post(
        "/api/v1/appointments/hold",
        json={
            "technician_id": sample_technician["id"],
            "work_order_id": wo_id,
            "scheduled_start": slot_start,
            "scheduled_end": slot_end,
            "customer_id": sample_customer["id"],
        },
        headers=headers,
    )
    assert hold_resp.status_code == 201
    hold_data = hold_resp.json()
    assert hold_data["status"] == "TENTATIVE_HOLD"
    token = hold_data["reservation_token"]

    # 4. Attempt to confirm WITHOUT explicit customer affirmation -> REJECTED
    unconfirmed_resp = await async_client.post(
        "/api/v1/appointments/confirm",
        json={
            "reservation_token": token,
            "user_confirmed": False,  # explicit confirmation missing!
        },
        headers=headers,
    )
    assert unconfirmed_resp.status_code == 422
    assert (
        "Explicit customer confirmation is required" in unconfirmed_resp.json()["error"]["message"]
    )

    # 5. Confirm with explicit affirmative confirmation -> SUCCESS
    confirm_resp = await async_client.post(
        "/api/v1/appointments/confirm",
        json={
            "reservation_token": token,
            "user_confirmed": True,
            "customer_notes": "Please call when 10 minutes away.",
        },
        headers=headers,
    )
    assert confirm_resp.status_code == 201
    confirmed_data = confirm_resp.json()
    assert confirmed_data["status"] == "CONFIRMED"
    assert confirmed_data["reservation_token"] == token

    # Work order status should now be SCHEDULED
    wo_check = await async_client.get(f"/api/v1/work-orders/{wo_id}", headers=headers)
    assert wo_check.json()["status"] == "SCHEDULED"


# ============================================================================
# 4. CONCURRENCY: SIMULTANEOUS BOOKING REQUESTS (RACE CONDITION)
# ============================================================================


async def test_simultaneous_concurrent_bookings_for_same_technician(
    async_client: AsyncClient,
    admin_token: str,
    sample_customer: dict,
    sample_technician: dict,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create two work orders
    wo1 = (
        await async_client.post(
            "/api/v1/work-orders",
            json={
                "customer_id": sample_customer["id"],
                "category": "HVAC",
                "priority": "HIGH",
                "description": "Job 1 for concurrent race test",
                "service_address": sample_customer["service_addresses"][0],
            },
            headers=headers,
        )
    ).json()

    wo2 = (
        await async_client.post(
            "/api/v1/work-orders",
            json={
                "customer_id": sample_customer["id"],
                "category": "HVAC",
                "priority": "HIGH",
                "description": "Job 2 for concurrent race test",
                "service_address": sample_customer["service_addresses"][0],
            },
            headers=headers,
        )
    ).json()

    # Exact same target window
    now = datetime.now(UTC)
    race_start = (now + timedelta(days=2, hours=10)).isoformat()
    race_end = (now + timedelta(days=2, hours=11, minutes=30)).isoformat()

    booking_payload_1 = {
        "technician_id": sample_technician["id"],
        "work_order_id": wo1["id"],
        "customer_id": sample_customer["id"],
        "scheduled_start": race_start,
        "scheduled_end": race_end,
    }
    booking_payload_2 = {
        "technician_id": sample_technician["id"],
        "work_order_id": wo2["id"],
        "customer_id": sample_customer["id"],
        "scheduled_start": race_start,
        "scheduled_end": race_end,
    }

    # Fire both booking requests concurrently via asyncio.gather
    results = await asyncio.gather(
        async_client.post("/api/v1/appointments", json=booking_payload_1, headers=headers),
        async_client.post("/api/v1/appointments", json=booking_payload_2, headers=headers),
    )

    status_codes = [r.status_code for r in results]

    # Database-enforced atomic reservation guarantees: exactly ONE 201, and ONE 409 Conflict
    assert 201 in status_codes, f"Expected one 201 success, got {status_codes}"
    assert 409 in status_codes, f"Expected one 409 conflict, got {status_codes}"


# ============================================================================
# 5. CANCELLATION & RESCHEDULING
# ============================================================================


async def test_appointment_cancellation_and_rescheduling(
    async_client: AsyncClient,
    admin_token: str,
    sample_customer: dict,
    sample_technician: dict,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create work order and appointment
    wo = (
        await async_client.post(
            "/api/v1/work-orders",
            json={
                "customer_id": sample_customer["id"],
                "category": "HVAC",
                "priority": "MEDIUM",
                "description": "Routine compressor check",
                "service_address": sample_customer["service_addresses"][0],
            },
            headers=headers,
        )
    ).json()

    now = datetime.now(UTC)
    start1 = now + timedelta(days=3, hours=9)
    end1 = start1 + timedelta(hours=1)

    appt = (
        await async_client.post(
            "/api/v1/appointments",
            json={
                "technician_id": sample_technician["id"],
                "work_order_id": wo["id"],
                "customer_id": sample_customer["id"],
                "scheduled_start": start1.isoformat(),
                "scheduled_end": end1.isoformat(),
            },
            headers=headers,
        )
    ).json()
    appt_id = appt["id"]

    # 2. Reschedule to afternoon
    start2 = now + timedelta(days=3, hours=14)
    end2 = start2 + timedelta(hours=1)

    resched_resp = await async_client.post(
        f"/api/v1/appointments/{appt_id}/reschedule",
        json={
            "new_scheduled_start": start2.isoformat(),
            "new_scheduled_end": end2.isoformat(),
            "reason": "Customer needs afternoon window",
        },
        headers=headers,
    )
    assert resched_resp.status_code == 200
    resched_data = resched_resp.json()
    assert resched_data["status"] == "CONFIRMED"
    assert resched_data["lock_version"] == 2

    # 3. Cancel the appointment
    cancel_resp = await async_client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"reason": "Customer resolved issue with circuit reset"},
        headers=headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Slot should now be freely re-bookable
    rebook_resp = await async_client.post(
        "/api/v1/appointments",
        json={
            "technician_id": sample_technician["id"],
            "work_order_id": wo["id"],
            "customer_id": sample_customer["id"],
            "scheduled_start": start2.isoformat(),
            "scheduled_end": end2.isoformat(),
        },
        headers=headers,
    )
    assert rebook_resp.status_code == 201


# ============================================================================
# 6. CRASH SAFETY, RETRIES & RECONCILIATION
# ============================================================================


async def test_retry_after_confirmation_returns_existing_booking(
    async_client: AsyncClient, admin_token: str, sample_customer: dict, sample_technician: dict
):
    """
    Verifies that retrying an appointment confirmation with the same reservation token
    safely returns the existing confirmed booking rather than raising an error or duplicating.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    wo = (
        await async_client.post(
            "/api/v1/work-orders",
            json={
                "customer_id": sample_customer["id"],
                "category": "PLUMBING",
                "priority": "MEDIUM",
                "description": "Bathroom sink drain clogged",
                "service_address": sample_customer["service_addresses"][0],
            },
            headers=headers,
        )
    ).json()

    now = datetime.now(UTC)
    sched_start = now + timedelta(days=4, hours=10)
    sched_end = sched_start + timedelta(hours=1)

    hold_resp = await async_client.post(
        "/api/v1/appointments/hold",
        json={
            "technician_id": sample_technician["id"],
            "work_order_id": wo["id"],
            "scheduled_start": sched_start.isoformat(),
            "scheduled_end": sched_end.isoformat(),
            "customer_id": sample_customer["id"],
        },
        headers=headers,
    )
    token = hold_resp.json()["reservation_token"]

    # First confirm
    confirm1 = await async_client.post(
        "/api/v1/appointments/confirm",
        json={"reservation_token": token, "user_confirmed": True},
        headers=headers,
    )
    assert confirm1.status_code == 201
    appt1 = confirm1.json()

    # Retry with same token (e.g. client dropped connection before receiving response)
    confirm2 = await async_client.post(
        "/api/v1/appointments/confirm",
        json={"reservation_token": token, "user_confirmed": True},
        headers=headers,
    )
    assert confirm2.status_code == 201
    appt2 = confirm2.json()

    assert appt1["id"] == appt2["id"]
    assert appt1["appointment_number"] == appt2["appointment_number"]
    assert appt2["status"] == "CONFIRMED"


async def test_expired_reservation_hold_rejected_and_released(
    async_client: AsyncClient,
    admin_token: str,
    sample_customer: dict,
    sample_technician: dict,
    test_db,
):
    """
    Verifies that attempting to confirm an expired hold rejects with 422 and frees technician calendar.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    wo_resp = await async_client.post(
        "/api/v1/work-orders",
        json={
            "customer_id": sample_customer["id"],
            "category": "PLUMBING",
            "priority": "ROUTINE",
            "description": "Ceiling fan replacement",
            "service_address": sample_customer["service_addresses"][0],
        },
        headers=headers,
    )
    assert wo_resp.status_code == 201, wo_resp.text
    wo = wo_resp.json()

    now = datetime.now(UTC)
    sched_start = now + timedelta(days=5, hours=9)
    sched_end = sched_start + timedelta(hours=1)

    hold_resp = await async_client.post(
        "/api/v1/appointments/hold",
        json={
            "technician_id": sample_technician["id"],
            "work_order_id": wo["id"],
            "scheduled_start": sched_start.isoformat(),
            "scheduled_end": sched_end.isoformat(),
            "customer_id": sample_customer["id"],
        },
        headers=headers,
    )
    token = hold_resp.json()["reservation_token"]

    # Backdate the hold expiration in the database
    past_time = now - timedelta(minutes=15)
    await test_db["slot_reservations"].update_one(
        {"reservation_token": token},
        {"$set": {"expires_at": past_time}},
    )

    # Attempt to confirm expired hold
    confirm_resp = await async_client.post(
        "/api/v1/appointments/confirm",
        json={"reservation_token": token, "user_confirmed": True},
        headers=headers,
    )
    assert confirm_resp.status_code == 422
    assert "expired" in confirm_resp.json()["error"]["message"].lower()

    # Verify technician active bookings released
    from bson import ObjectId

    tech_doc = await test_db["technicians"].find_one({"_id": ObjectId(sample_technician["id"])})
    assert tech_doc is not None
    assert not any(b.get("booking_id") == token for b in tech_doc.get("active_bookings", []))

    # Slot can now be re-held freely
    re_hold = await async_client.post(
        "/api/v1/appointments/hold",
        json={
            "technician_id": sample_technician["id"],
            "work_order_id": wo["id"],
            "scheduled_start": sched_start.isoformat(),
            "scheduled_end": sched_end.isoformat(),
            "customer_id": sample_customer["id"],
        },
        headers=headers,
    )
    assert re_hold.status_code == 201

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.core.config import settings
from app.integrations.calendar import get_calendar_provider
from app.integrations.calendar.protocol import CalendarEventPayload
from app.integrations.crm import get_crm_provider
from app.integrations.crm.protocol import CRMCustomerPayload, CRMWorkOrderPayload
from app.integrations.notifications import get_notification_provider
from app.repositories.outbox_repo import OutboxRepository
from app.schemas.outbox import OutboxEventCreate, OutboxEventStatus, OutboxEventType
from app.services.notification_templates import (
    NotificationTemplateService,
    NotificationTemplateType,
)
from app.services.outbox_service import OutboxService

# ============================================================================
# 1. NOTIFICATION TEMPLATES TESTS
# ============================================================================


def test_notification_templates_rendering():
    ctx = {
        "customer_name": "Eleanor Vance",
        "category": "HVAC",
        "technician_name": "Marcus Vance",
        "scheduled_time": "Friday, Oct 16 at 02:00 PM",
        "scheduled_date": "2026-10-16",
        "new_scheduled_time": "Monday, Oct 19 at 10:00 AM",
        "service_address": "742 Evergreen Terrace, Atlanta, GA",
        "work_order_number": "WO-2026-1001",
        "reason": "Customer schedule change",
        "completion_notes": "Replaced blower capacitor and recharged R410A.",
    }

    # Test all 7 lifecycle templates
    for t_type in NotificationTemplateType:
        rendered = NotificationTemplateService.render(t_type, ctx)
        assert len(rendered.sms_body) > 10
        assert len(rendered.email_subject) > 5
        assert len(rendered.email_html) > 20
        assert len(rendered.email_text) > 20
        assert (
            "Eleanor Vance" in rendered.email_text
            or "Eleanor Vance" in rendered.sms_body
            or "Marcus Vance" in rendered.sms_body
        )


# ============================================================================
# 2. TRANSACTIONAL OUTBOX: STAGING, PROCESSING, & LIFECYCLE
# ============================================================================


async def test_outbox_staging_and_processing_lifecycle(test_db):
    repo = OutboxRepository(test_db)
    service = OutboxService(repo)
    mock_notif = get_notification_provider()
    mock_notif.clear()

    # 1. Stage an outbox event
    event_in = OutboxEventCreate(
        event_type=OutboxEventType.NOTIFICATION_BOOKING_CONFIRMED,
        aggregate_type="Appointment",
        aggregate_id="test_appt_123",
        payload={
            "to_phone": "+14045550101",
            "to_email": "customer@example.com",
            "channel": "BOTH",
            "context": {
                "customer_name": "Arthur Dent",
                "category": "PLUMBING",
                "technician_name": "Bob Vance",
                "scheduled_time": "Tomorrow at 10 AM",
            },
        },
        idempotency_key="idemp_test_event_001",
    )
    staged = await repo.stage_event(event_in)
    assert staged["status"] == OutboxEventStatus.PENDING.value
    assert staged["event_id"] is not None

    # Duplicate staging with same idempotency_key returns existing event
    dup = await repo.stage_event(event_in)
    assert dup["event_id"] == staged["event_id"]

    # 2. Process batch
    result = await service.process_batch(limit=10)
    assert result["batch_size"] == 1
    assert result["succeeded"] == 1
    assert result["failed"] == 0

    # 3. Verify in repository
    completed = await repo.collection.find_one({"event_id": staged["event_id"]})
    assert completed["status"] == OutboxEventStatus.SENT.value
    assert completed["external_reference_id"] is not None
    assert completed["processed_at"] is not None

    # 4. Verify mock notification adapter received both SMS and email
    assert len(mock_notif.sent_sms) == 1
    assert mock_notif.sent_sms[0]["to_phone"] == "+14045550101"
    assert len(mock_notif.sent_emails) == 1
    assert mock_notif.sent_emails[0]["to_email"] == "customer@example.com"


# ============================================================================
# 3. EXPONENTIAL BACKOFF, JITTER, & RETRIES
# ============================================================================


async def test_outbox_exponential_backoff_and_jitter(test_db):
    repo = OutboxRepository(test_db)
    service = OutboxService(repo)
    mock_notif = get_notification_provider()
    mock_notif.clear()

    # Simulate 2 transient failures
    mock_notif.simulate_transient_failures(count=2, reason="Simulated upstream network glitch")

    event_in = OutboxEventCreate(
        event_type=OutboxEventType.NOTIFICATION_REMINDER_24H,
        aggregate_type="Appointment",
        aggregate_id="test_appt_retry",
        payload={
            "to_phone": "+14045550202",
            "channel": "SMS",
            "context": {"customer_name": "Test User", "scheduled_time": "10:00 AM"},
        },
        max_retries=5,
    )
    staged = await repo.stage_event(event_in)
    event_id = staged["event_id"]

    # Attempt 1: Should fail and schedule retry with backoff + jitter
    res1 = await service.process_batch(limit=10)
    assert res1["failed"] == 1

    doc1 = await repo.collection.find_one({"event_id": event_id})
    assert doc1["status"] == OutboxEventStatus.FAILED.value
    assert doc1["retry_count"] == 1
    assert "Simulated upstream network glitch" in doc1["last_error"]
    assert doc1["next_retry_at"] > doc1["created_at"]

    # Manually wind next_retry_at back to now to simulate time passing
    now = datetime.now(UTC)
    await repo.collection.update_one({"event_id": event_id}, {"$set": {"next_retry_at": now}})

    # Attempt 2: Second transient failure
    res2 = await service.process_batch(limit=10)
    assert res2["failed"] == 1
    doc2 = await repo.collection.find_one({"event_id": event_id})
    assert doc2["retry_count"] == 2

    # Manually wind time back again
    await repo.collection.update_one({"event_id": event_id}, {"$set": {"next_retry_at": now}})

    # Attempt 3: Should succeed now that transient failures are exhausted
    res3 = await service.process_batch(limit=10)
    assert res3["succeeded"] == 1
    doc3 = await repo.collection.find_one({"event_id": event_id})
    assert doc3["status"] == OutboxEventStatus.SENT.value
    assert doc3["last_error"] is None


# ============================================================================
# 4. DEAD-LETTER QUEUE & SAFE REPLAY
# ============================================================================


async def test_dead_letter_queue_and_safe_replay(test_db):
    repo = OutboxRepository(test_db)
    service = OutboxService(repo)
    mock_notif = get_notification_provider()
    mock_notif.clear()

    # Simulate permanent failure with max_retries = 2
    mock_notif.simulate_transient_failures(count=5, reason="Simulated dead letter cause")

    event_in = OutboxEventCreate(
        event_type=OutboxEventType.NOTIFICATION_APPOINTMENT_CANCELLED,
        aggregate_type="Appointment",
        aggregate_id="test_appt_dlq",
        payload={"to_phone": "+14045550303", "channel": "SMS", "context": {"reason": "Cancelled"}},
        max_retries=2,
    )
    staged = await repo.stage_event(event_in)
    event_id = staged["event_id"]

    # Attempt 1: Fails, retry_count = 1
    await service.process_batch(limit=10)
    await repo.collection.update_one(
        {"event_id": event_id}, {"$set": {"next_retry_at": datetime.now(UTC)}}
    )

    # Attempt 2: Reaches max_retries (2) -> transitions to DEAD_LETTER
    await service.process_batch(limit=10)
    doc_dlq = await repo.collection.find_one({"event_id": event_id})
    assert doc_dlq["status"] == OutboxEventStatus.DEAD_LETTER.value
    assert doc_dlq["retry_count"] == 2

    # Verify dead letter event is not picked up in regular batch processing
    empty_batch = await service.process_batch(limit=10)
    assert empty_batch["batch_size"] == 0

    # Safe Replay: Reset to PENDING
    mock_notif.clear()  # Clear failure simulation
    replayed = await repo.replay_dead_letter(event_id)
    assert replayed is not None
    assert replayed["status"] == OutboxEventStatus.PENDING.value
    assert replayed["retry_count"] == 0

    # Process again -> Should now succeed
    res_replayed = await service.process_batch(limit=10)
    assert res_replayed["succeeded"] == 1
    final_doc = await repo.collection.find_one({"event_id": event_id})
    assert final_doc["status"] == OutboxEventStatus.SENT.value


# ============================================================================
# 5. TIMEOUTS & RATE LIMITS
# ============================================================================


async def test_timeouts_and_rate_limits(test_db):
    repo = OutboxRepository(test_db)
    service = OutboxService(repo)
    mock_notif = get_notification_provider()
    mock_notif.clear()

    # 1. Rate limit test (HTTP 429)
    mock_notif.simulate_rate_limit(enabled=True, reset_seconds=5)
    e1 = await repo.stage_event(
        OutboxEventCreate(
            event_type=OutboxEventType.NOTIFICATION_REMINDER_2H,
            aggregate_type="Appointment",
            aggregate_id="rl_test",
            payload={"to_phone": "+14045550404", "channel": "SMS", "context": {}},
        )
    )
    await service.process_batch(limit=10)
    doc_rl = await repo.collection.find_one({"event_id": e1["event_id"]})
    assert doc_rl["status"] == OutboxEventStatus.FAILED.value
    assert "Rate limit exceeded" in doc_rl["last_error"]

    # 2. Timeout test
    mock_notif.clear()
    mock_notif.simulate_timeout(enabled=True)
    e2 = await repo.stage_event(
        OutboxEventCreate(
            event_type=OutboxEventType.NOTIFICATION_REMINDER_2H,
            aggregate_type="Appointment",
            aggregate_id="timeout_test",
            payload={"to_phone": "+14045550505", "channel": "SMS", "context": {}},
        )
    )
    await service.process_batch(limit=10)
    doc_to = await repo.collection.find_one({"event_id": e2["event_id"]})
    assert doc_to["status"] == OutboxEventStatus.FAILED.value
    assert "Simulated SMS gateway timeout" in doc_to["last_error"]

    mock_notif.clear()


# ============================================================================
# 6. WEBHOOKS: AUTHENTICATION, REPLAY PROTECTION, & DEDUPLICATION
# ============================================================================


async def test_webhook_signature_and_replay_protection(async_client: AsyncClient, test_db):
    secret = settings.WEBHOOK_SIGNING_SECRET.encode("utf-8")
    payload = json.dumps({"id": "evt_tw_999", "event": "delivered", "provider": "twilio"}).encode(
        "utf-8"
    )
    now_ts = str(datetime.now(UTC).timestamp())

    # 1. Valid signature & fresh timestamp -> SUCCESS (200)
    valid_sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    resp_valid = await async_client.post(
        "/api/v1/webhooks/notifications",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Signature": f"sha256={valid_sig}",
            "X-Timestamp": now_ts,
        },
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["duplicate"] is False

    # 2. Invalid signature -> REJECTED (401)
    resp_bad_sig = await async_client.post(
        "/api/v1/webhooks/notifications",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Signature": "sha256=invalidhexsignature1234567890",
            "X-Timestamp": now_ts,
        },
    )
    assert resp_bad_sig.status_code == 401

    # 3. Expired timestamp (> 300s old) -> REJECTED (401 Replay Protection)
    old_ts = str((datetime.now(UTC) - timedelta(seconds=600)).timestamp())
    resp_replay = await async_client.post(
        "/api/v1/webhooks/notifications",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Signature": f"sha256={valid_sig}",
            "X-Timestamp": old_ts,
        },
    )
    assert resp_replay.status_code == 401

    # 4. Duplicate webhook delivery -> Idempotent response with duplicate=True
    resp_dup = await async_client.post(
        "/api/v1/webhooks/notifications",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Signature": f"sha256={valid_sig}",
            "X-Timestamp": now_ts,
        },
    )
    assert resp_dup.status_code == 200
    assert resp_dup.json()["duplicate"] is True
    assert resp_dup.json()["status"] == "acknowledged"


# ============================================================================
# 7. WORKER CRASH RECOVERY (STUCK IN_FLIGHT RECLAIM)
# ============================================================================


async def test_worker_crash_recovery(test_db):
    repo = OutboxRepository(test_db)
    service = OutboxService(repo)
    mock_notif = get_notification_provider()
    mock_notif.clear()

    # Create event stuck in IN_FLIGHT older than 5 minutes (worker died)
    now = datetime.now(UTC)
    stuck_time = now - timedelta(minutes=10)
    event_doc = {
        "event_id": "stuck_worker_evt_1",
        "event_type": OutboxEventType.NOTIFICATION_BOOKING_CONFIRMED.value,
        "aggregate_type": "Appointment",
        "aggregate_id": "appt_recovered",
        "payload": {
            "to_phone": "+14045550606",
            "channel": "SMS",
            "context": {"customer_name": "Crash Recovery", "scheduled_time": "12:00 PM"},
        },
        "status": OutboxEventStatus.IN_FLIGHT.value,
        "retry_count": 0,
        "max_retries": 5,
        "next_retry_at": stuck_time,
        "locked_by": "crashed_worker_99",
        "created_at": stuck_time,
        "updated_at": stuck_time,
    }
    await repo.collection.insert_one(event_doc)

    # Next batch execution should reclaim stuck event and deliver it
    res = await service.process_batch(limit=10, worker_id="recovery_worker_1")
    assert res["batch_size"] == 1
    assert res["succeeded"] == 1

    recovered_doc = await repo.collection.find_one({"event_id": "stuck_worker_evt_1"})
    assert recovered_doc["status"] == OutboxEventStatus.SENT.value
    assert recovered_doc["locked_by"] == "recovery_worker_1"


# ============================================================================
# 8. CALENDAR & CRM ADAPTER CONTRACTS
# ============================================================================


async def test_calendar_and_crm_adapters_contracts():
    cal = get_calendar_provider()
    now = datetime.now(UTC)

    # Calendar Create & Update
    payload = CalendarEventPayload(
        title="Test HVAC Service",
        description="Replace thermostat",
        start_time=now,
        end_time=now + timedelta(hours=1),
        location="Atlanta, GA",
        attendee_emails=["tech@fieldops.ai", "client@example.com"],
    )
    cal_res = await cal.create_event(payload)
    assert cal_res.success is True
    assert cal_res.external_event_id.startswith("cal_evt_")

    update_res = await cal.update_event(cal_res.external_event_id, payload)
    assert update_res.success is True

    # CRM Customer & Ticket Sync
    crm = get_crm_provider()
    cust_res = await crm.sync_customer(
        CRMCustomerPayload(
            internal_customer_id="cust_1",
            name="John Doe",
            email="john@example.com",
            phone="+14045550707",
            service_address="123 Main St",
        )
    )
    assert cust_res.success is True
    assert cust_res.external_record_id.startswith("crm_cust_")

    wo_res = await crm.sync_work_order(
        CRMWorkOrderPayload(
            internal_work_order_id="wo_1",
            work_order_number="WO-2026-9999",
            customer_id="cust_1",
            category="HVAC",
            priority="HIGH",
            status="COMPLETED",
            description="Replaced compressor",
        )
    )
    assert wo_res.success is True
    assert wo_res.external_record_id.startswith("crm_ticket_")


# ============================================================================
# 9. INTEGRATIONS API ENDPOINTS & METRICS
# ============================================================================


async def test_integrations_api_endpoints_and_metrics(
    async_client: AsyncClient, admin_token: str, test_db
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. GET /api/v1/integrations/status
    status_resp = await async_client.get("/api/v1/integrations/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["notification_provider"] == "mock"
    assert status_data["maps_provider"] == "mock"
    assert status_data["calendar_provider"] == "mock"
    assert status_data["crm_provider"] == "mock"

    # 2. GET /api/v1/integrations/metrics
    metrics_resp = await async_client.get("/api/v1/integrations/metrics", headers=headers)
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert "total_events" in metrics_data
    assert "dead_letter" in metrics_data

    # 3. Stage a dead letter event and query dead-letter endpoint
    repo = OutboxRepository(test_db)
    now = datetime.now(UTC)
    dlq_event = {
        "event_id": "test_dlq_api_evt",
        "event_type": OutboxEventType.NOTIFICATION_REMINDER_2H.value,
        "aggregate_type": "Appointment",
        "aggregate_id": "appt_test_dlq",
        "payload": {},
        "status": OutboxEventStatus.DEAD_LETTER.value,
        "retry_count": 5,
        "max_retries": 5,
        "next_retry_at": now + timedelta(days=365),
        "created_at": now,
        "updated_at": now,
    }
    await repo.collection.insert_one(dlq_event)

    dlq_resp = await async_client.get("/api/v1/integrations/outbox/dead-letter", headers=headers)
    assert dlq_resp.status_code == 200
    dlq_items = dlq_resp.json()
    assert any(it["event_id"] == "test_dlq_api_evt" for it in dlq_items)

    # 4. POST /api/v1/integrations/outbox/replay/{id}
    replay_resp = await async_client.post(
        "/api/v1/integrations/outbox/replay/test_dlq_api_evt", headers=headers
    )
    assert replay_resp.status_code == 200
    assert replay_resp.json()["event"]["status"] == "PENDING"

    # 5. POST /api/v1/integrations/outbox/process
    proc_resp = await async_client.post("/api/v1/integrations/outbox/process", headers=headers)
    assert proc_resp.status_code == 200
    assert "batch_size" in proc_resp.json()


# ============================================================================
# 10. CELERY TASKS DIRECT INVOCATION
# ============================================================================


def test_celery_task_definitions():
    import app.tasks  # noqa: F401
    from app.core.celery_app import celery_app

    # Ensure celery tasks are registered with correct task names
    registered = list(celery_app.tasks.keys())
    assert "app.tasks.outbox_tasks.process_outbox_batch_task" in registered
    assert "app.tasks.notification_tasks.check_upcoming_appointment_reminders_task" in registered
    assert "app.tasks.maintenance_tasks.cleanup_expired_reservations_task" in registered

    # Verify beat schedule configuration
    beat_schedule = celery_app.conf.beat_schedule
    assert "process-outbox-events-periodic" in beat_schedule
    assert "check-upcoming-reminders-periodic" in beat_schedule
    assert "cleanup-expired-holds-periodic" in beat_schedule

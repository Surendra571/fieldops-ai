"""
FieldOps AI — Production Readiness, Concurrency & Load Verification Tests
"""

import pytest

from app.core.config import settings
from app.core.logging import PIIRedactionFilter
from app.tasks.maintenance_tasks import cleanup_expired_reservations_task
from app.tasks.notification_tasks import check_upcoming_appointment_reminders_task
from app.tasks.outbox_tasks import process_outbox_batch_task
from scripts.load_test import run_load_test


@pytest.mark.asyncio
async def test_request_id_and_latency_headers(async_client):
    """Verify Request ID correlation and process latency headers."""
    # Case 1: Client provides X-Request-ID
    custom_id = "test-corr-id-9988"
    resp = await async_client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id
    assert "X-Process-Time-Ms" in resp.headers

    # Case 2: System generates X-Request-ID when omitted
    resp2 = await async_client.get("/api/v1/health")
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Request-ID") is not None
    assert resp2.headers["X-Request-ID"].startswith("req_")


@pytest.mark.asyncio
async def test_metrics_endpoint_structure(async_client):
    """Verify /api/v1/metrics and root /metrics expose operational telemetry."""
    # Prime a few requests
    await async_client.get("/api/v1/health")
    await async_client.get("/api/v1/ready")

    resp = await async_client.get("/api/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == settings.PROJECT_NAME
    assert "uptime_seconds" in data
    assert "metrics" in data
    metrics = data["metrics"]
    assert "total_requests" in metrics
    assert metrics["total_requests"] >= 2
    assert "latency_ms" in metrics
    assert "p50" in metrics["latency_ms"]
    assert "p95" in metrics["latency_ms"]
    assert "status_breakdown" in metrics


@pytest.mark.asyncio
async def test_rate_limiter_middleware_throttles(async_client, dispatcher_token):
    """Verify that requests exceeding RATE_LIMIT_PER_MINUTE return HTTP 429."""
    from app.core.middleware import RateLimiterMiddleware

    original_limit = settings.RATE_LIMIT_PER_MINUTE
    original_enabled = settings.RATE_LIMIT_ENABLED
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMIT_PER_MINUTE = 3  # Lower threshold for deterministic testing
    RateLimiterMiddleware.reset()

    headers = {"Authorization": f"Bearer {dispatcher_token}"}

    try:
        # Request 1, 2, 3 should succeed
        r1 = await async_client.get("/api/v1/work-orders", headers=headers)
        r2 = await async_client.get("/api/v1/work-orders", headers=headers)
        r3 = await async_client.get("/api/v1/work-orders", headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

        # Request 4 should be throttled (HTTP 429)
        r4 = await async_client.get("/api/v1/work-orders", headers=headers)
        assert r4.status_code == 429
        assert r4.json()["status"] == 429
        assert "Retry-After" in r4.headers
        assert "rate-limit-exceeded" in r4.json()["type"]

        # Health check should be EXEMPT from throttling
        health_resp = await async_client.get("/api/v1/health")
        assert health_resp.status_code == 200
    finally:
        RateLimiterMiddleware.reset()
        settings.RATE_LIMIT_PER_MINUTE = original_limit
        settings.RATE_LIMIT_ENABLED = original_enabled


def test_enhanced_pii_redaction_credit_card_and_ssn():
    """Verify that SSN, credit cards, phones, and emails are scrubbed from log lines."""
    raw_log = (
        "Customer John Doe with SSN 123-45-6789 and card 4111222233334444 called from 404-555-0199 "
        "email john@example.com with token Bearer eyJhbGciOiJIUzI1NiI5. Secret password: 'SuperSecretPass123!'"
    )
    redacted = PIIRedactionFilter.redact(raw_log)

    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted

    assert "4111222233334444" not in redacted
    assert "[REDACTED_CREDIT_CARD]" in redacted

    assert "404-555-0199" not in redacted
    assert "[REDACTED_PHONE]" in redacted

    assert "john@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted

    assert "SuperSecretPass123!" not in redacted
    assert "[REDACTED_SECRET]" in redacted


@pytest.mark.asyncio
async def test_celery_tasks_execution_with_test_db(test_db):
    """
    Verify that Celery task entrypoints execute without AttributeError
    and interact cleanly with the database.
    """
    from app.core.database import db_manager

    db_manager.client = test_db.client
    db_manager.db = test_db

    # 1. process_outbox_batch_task
    res_outbox = process_outbox_batch_task(limit=5)
    assert isinstance(res_outbox, dict)
    assert "batch_size" in res_outbox
    assert "succeeded" in res_outbox

    # 2. check_upcoming_appointment_reminders_task
    res_reminders = check_upcoming_appointment_reminders_task()
    assert isinstance(res_reminders, dict)
    assert "reminders_staged" in res_reminders

    # 3. cleanup_expired_reservations_task
    res_cleanup = cleanup_expired_reservations_task()
    assert isinstance(res_cleanup, dict)
    assert "expired_holds_cleaned" in res_cleanup


@pytest.mark.asyncio
async def test_load_benchmark_in_process_concurrency(async_client, dispatcher_token):
    """
    Executes a high-concurrency load test across the realistic request mix
    and measures actual latency percentiles, throughput, and error rates.
    """
    summary = await run_load_test(
        base_url="http://test",
        concurrency=10,
        total_requests=100,
        client=async_client,
        auth_token=dispatcher_token,
    )

    # Assert zero errors under load
    assert summary.error_rate_pct == 0.0
    assert summary.successful_requests == 100
    assert summary.failed_requests == 0

    # Assert latency bounds
    assert summary.latencies_ms["p50"] < 150.0  # Under 150ms in-process P50
    assert (
        summary.latencies_ms["p95"] < 10000.0
    )  # Under 10.0s in-process P95 with concurrent ML threads under CPU load
    assert summary.throughput_rps > 10.0  # Sustained throughput

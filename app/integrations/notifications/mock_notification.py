import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.integrations.notifications.protocol import (
    DeliveryStatus,
    NotificationProviderProtocol,
    NotificationResult,
)


class MockNotificationAdapter(NotificationProviderProtocol):
    """
    Deterministic, in-memory notification adapter.
    Enables reliable testing of delivery, retries, rate limits, timeouts, and failures.
    """

    def __init__(self):
        self.sent_sms: list[dict[str, Any]] = []
        self.sent_emails: list[dict[str, Any]] = []
        self._simulate_failure: bool = False
        self._simulate_timeout: bool = False
        self._simulate_rate_limit: bool = False
        self._failure_reason: str = "Simulated upstream provider failure"
        self._fail_count_remaining: int = 0
        self._rate_limit_reset_seconds: int = 2

    def simulate_transient_failures(self, count: int, reason: str = "Transient upstream failure"):
        """Simulate failing the next `count` calls, then succeeding."""
        self._fail_count_remaining = count
        self._failure_reason = reason

    def simulate_rate_limit(self, enabled: bool = True, reset_seconds: int = 2):
        self._simulate_rate_limit = enabled
        self._rate_limit_reset_seconds = reset_seconds

    def simulate_timeout(self, enabled: bool = True):
        self._simulate_timeout = enabled

    def clear(self):
        self.sent_sms.clear()
        self.sent_emails.clear()
        self._simulate_failure = False
        self._simulate_timeout = False
        self._simulate_rate_limit = False
        self._fail_count_remaining = 0

    async def send_sms(
        self,
        to_phone: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        if self._simulate_timeout:
            await asyncio.sleep(0.01)
            raise TimeoutError("Simulated SMS gateway timeout")

        if self._simulate_rate_limit:
            return NotificationResult(
                success=False,
                provider="mock_twilio",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message=f"Rate limit exceeded (HTTP 429). Retry after {self._rate_limit_reset_seconds}s.",
                metadata={"retry_after": self._rate_limit_reset_seconds},
            )

        if self._fail_count_remaining > 0:
            self._fail_count_remaining -= 1
            return NotificationResult(
                success=False,
                provider="mock_twilio",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message=self._failure_reason,
            )

        msg_id = f"mock_sms_{uuid.uuid4().hex[:12]}"
        record = {
            "id": msg_id,
            "to_phone": to_phone,
            "body": body,
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self.sent_sms.append(record)

        return NotificationResult(
            success=True,
            provider="mock_twilio",
            provider_message_id=msg_id,
            status=DeliveryStatus.DELIVERED,
            delivered_at=record["sent_at"],
            metadata=record["metadata"],
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        if self._simulate_timeout:
            await asyncio.sleep(0.01)
            raise TimeoutError("Simulated email gateway timeout")

        if self._simulate_rate_limit:
            return NotificationResult(
                success=False,
                provider="mock_sendgrid",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message=f"Rate limit exceeded (HTTP 429). Retry after {self._rate_limit_reset_seconds}s.",
                metadata={"retry_after": self._rate_limit_reset_seconds},
            )

        if self._fail_count_remaining > 0:
            self._fail_count_remaining -= 1
            return NotificationResult(
                success=False,
                provider="mock_sendgrid",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message=self._failure_reason,
            )

        msg_id = f"mock_email_{uuid.uuid4().hex[:12]}"
        record = {
            "id": msg_id,
            "to_email": to_email,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text or "",
            "metadata": metadata or {},
            "sent_at": datetime.now(UTC),
        }
        self.sent_emails.append(record)

        return NotificationResult(
            success=True,
            provider="mock_sendgrid",
            provider_message_id=msg_id,
            status=DeliveryStatus.DELIVERED,
            delivered_at=record["sent_at"],
            metadata=record["metadata"],
        )

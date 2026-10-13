from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


class DeliveryStatus(str, Enum):
    DELIVERED = "DELIVERED"
    PENDING = "PENDING"
    FAILED = "FAILED"
    UNDELIVERABLE = "UNDELIVERABLE"


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    provider: str
    provider_message_id: str
    status: DeliveryStatus
    error_message: str | None = None
    delivered_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class NotificationProviderProtocol(Protocol):
    """
    Provider-independent interface for SMS and Email messaging.
    """

    async def send_sms(
        self,
        to_phone: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send an SMS message to a customer or technician."""
        ...

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send a transactional email."""
        ...

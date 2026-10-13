from app.core.config import settings
from app.integrations.notifications.mock_notification import MockNotificationAdapter
from app.integrations.notifications.protocol import (
    DeliveryStatus,
    NotificationProviderProtocol,
    NotificationResult,
)
from app.integrations.notifications.twilio_sendgrid import TwilioSendGridNotificationAdapter

_mock_instance: MockNotificationAdapter | None = None


def get_notification_provider() -> NotificationProviderProtocol:
    global _mock_instance
    if settings.NOTIFICATION_PROVIDER == "twilio_sendgrid":
        return TwilioSendGridNotificationAdapter()
    if _mock_instance is None:
        _mock_instance = MockNotificationAdapter()
    return _mock_instance


__all__ = [
    "DeliveryStatus",
    "MockNotificationAdapter",
    "NotificationProviderProtocol",
    "NotificationResult",
    "TwilioSendGridNotificationAdapter",
    "get_notification_provider",
]

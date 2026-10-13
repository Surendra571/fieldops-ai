import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.notifications.protocol import (
    DeliveryStatus,
    NotificationProviderProtocol,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class TwilioSendGridNotificationAdapter(NotificationProviderProtocol):
    """
    Production-ready integration adapter for Twilio (SMS) and SendGrid (Email).
    Requires valid API credentials configured via environment variables.
    """

    def __init__(
        self,
        twilio_account_sid: str = "",
        twilio_auth_token: str = "",
        twilio_from_number: str = "",
        sendgrid_api_key: str = "",
        sendgrid_from_email: str = "",
    ):
        self.twilio_account_sid = twilio_account_sid or settings.TWILIO_ACCOUNT_SID
        self.twilio_auth_token = twilio_auth_token or settings.TWILIO_AUTH_TOKEN
        self.twilio_from_number = twilio_from_number or settings.TWILIO_FROM_NUMBER
        self.sendgrid_api_key = sendgrid_api_key or settings.SENDGRID_API_KEY
        self.sendgrid_from_email = (
            sendgrid_from_email or settings.SENDGRID_FROM_EMAIL or "notifications@fieldops.ai"
        )

    async def send_sms(
        self,
        to_phone: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        if not (self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number):
            return NotificationResult(
                success=False,
                provider="twilio",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message="Twilio credentials not configured. Please supply TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.",
            )

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
        data = {
            "From": self.twilio_from_number,
            "To": to_phone,
            "Body": body,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    data=data,
                    auth=(self.twilio_account_sid, self.twilio_auth_token),
                )
                if resp.status_code in (200, 201):
                    res_json = resp.json()
                    return NotificationResult(
                        success=True,
                        provider="twilio",
                        provider_message_id=res_json.get("sid", ""),
                        status=DeliveryStatus.DELIVERED,
                        delivered_at=datetime.now(UTC),
                        metadata={"status": res_json.get("status")},
                    )
                elif resp.status_code == 429:
                    return NotificationResult(
                        success=False,
                        provider="twilio",
                        provider_message_id="",
                        status=DeliveryStatus.FAILED,
                        error_message="Twilio rate limit exceeded (HTTP 429).",
                        metadata={"retry_after": int(resp.headers.get("Retry-After", "5"))},
                    )
                else:
                    return NotificationResult(
                        success=False,
                        provider="twilio",
                        provider_message_id="",
                        status=DeliveryStatus.FAILED,
                        error_message=f"Twilio error {resp.status_code}: {resp.text}",
                    )
        except httpx.TimeoutException:
            return NotificationResult(
                success=False,
                provider="twilio",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message="Twilio API request timed out after 10s.",
            )
        except Exception as exc:
            return NotificationResult(
                success=False,
                provider="twilio",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message=f"Twilio transport error: {str(exc)}",
            )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        if not self.sendgrid_api_key:
            return NotificationResult(
                success=False,
                provider="sendgrid",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message="SendGrid API key not configured. Please supply SENDGRID_API_KEY.",
            )

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {self.sendgrid_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.sendgrid_from_email, "name": "FieldOps AI"},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": body_text or body_html},
                {"type": "text/html", "value": body_html},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in (200, 202):
                    msg_id = resp.headers.get("X-Message-Id", f"sg_{datetime.now(UTC).timestamp()}")
                    return NotificationResult(
                        success=True,
                        provider="sendgrid",
                        provider_message_id=msg_id,
                        status=DeliveryStatus.DELIVERED,
                        delivered_at=datetime.now(UTC),
                    )
                elif resp.status_code == 429:
                    return NotificationResult(
                        success=False,
                        provider="sendgrid",
                        provider_message_id="",
                        status=DeliveryStatus.FAILED,
                        error_message="SendGrid rate limit exceeded (HTTP 429).",
                        metadata={"retry_after": int(resp.headers.get("Retry-After", "5"))},
                    )
                else:
                    return NotificationResult(
                        success=False,
                        provider="sendgrid",
                        provider_message_id="",
                        status=DeliveryStatus.FAILED,
                        error_message=f"SendGrid error {resp.status_code}: {resp.text}",
                    )
        except httpx.TimeoutException:
            return NotificationResult(
                success=False,
                provider="sendgrid",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message="SendGrid API request timed out after 10s.",
            )
        except Exception as exc:
            return NotificationResult(
                success=False,
                provider="sendgrid",
                provider_message_id="",
                status=DeliveryStatus.FAILED,
                error_message=f"SendGrid transport error: {str(exc)}",
            )

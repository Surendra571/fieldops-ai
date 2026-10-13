import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Handles secure webhook ingestion:
    - HMAC-SHA256 signature verification
    - Timestamp replay protection (5-minute tolerance)
    - Deduplication of incoming delivery receipts and status notifications
    """

    def __init__(self, db: Any):
        self.db = db
        self.collection = db["webhook_events"]

    @classmethod
    def verify_signature(
        cls,
        payload_bytes: bytes,
        signature_header: str | None,
        timestamp_header: str | None = None,
        secret: str | None = None,
    ) -> bool:
        """
        Verify HMAC-SHA256 signature and replay protection timestamp.
        """
        signing_secret = (secret or settings.WEBHOOK_SIGNING_SECRET).encode("utf-8")
        if not signature_header:
            return False

        # 1. Replay protection check
        if timestamp_header:
            try:
                # Accept float epoch or ISO 8601
                if timestamp_header.replace(".", "", 1).isdigit():
                    ts = float(timestamp_header)
                else:
                    ts = datetime.fromisoformat(timestamp_header).timestamp()
                now_ts = datetime.now(UTC).timestamp()
                if abs(now_ts - ts) > settings.WEBHOOK_TOLERANCE_SECONDS:
                    logger.warning(
                        f"Webhook rejected: timestamp {ts} exceeds tolerance {settings.WEBHOOK_TOLERANCE_SECONDS}s"
                    )
                    return False
            except Exception as e:
                logger.warning(f"Webhook timestamp parse error: {e}")
                return False

        # 2. Compute expected HMAC
        expected_sig = hmac.new(signing_secret, payload_bytes, hashlib.sha256).hexdigest()

        # Clean header (handles "sha256=..." prefix if present)
        clean_sig = signature_header.removeprefix("sha256=")

        return hmac.compare_digest(expected_sig, clean_sig)

    async def ingest_event(
        self,
        provider: str,
        webhook_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Idempotently ingest and process a webhook event.
        Returns a result indicating whether this was newly processed or a duplicate.
        """
        # Deduplication check
        existing = await self.collection.find_one({"webhook_id": webhook_id, "provider": provider})
        if existing:
            logger.info(f"Duplicate webhook {webhook_id} from {provider} ignored.")
            return {
                "status": "acknowledged",
                "duplicate": True,
                "webhook_id": webhook_id,
                "provider": provider,
            }

        now = datetime.now(UTC)
        doc = {
            "webhook_id": webhook_id,
            "provider": provider,
            "event_type": event_type,
            "payload": payload,
            "processed_at": now,
        }
        await self.collection.insert_one(doc)

        # Process side effects based on provider and event
        await self._process_webhook_side_effect(provider, event_type, payload)

        return {
            "status": "processed",
            "duplicate": False,
            "webhook_id": webhook_id,
            "provider": provider,
        }

    async def _process_webhook_side_effect(
        self, provider: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        """
        Update message delivery statuses or CRM synchronization states.
        """
        if provider == "twilio":
            sms_sid = payload.get("MessageSid") or payload.get("SmsSid")
            sms_status = payload.get("MessageStatus") or payload.get("SmsStatus")
            if sms_sid and sms_status:
                await self.db["outbox_events"].update_one(
                    {"external_reference_id": sms_sid},
                    {
                        "$set": {
                            "delivery_status": sms_status,
                            "delivery_updated_at": datetime.now(UTC),
                        }
                    },
                )
        elif provider == "sendgrid":
            # Event webhook array
            events = payload.get("events", [payload])
            for ev in events:
                sg_id = ev.get("sg_message_id", "").split(".")[0]
                event_name = ev.get("event")
                if sg_id and event_name:
                    await self.db["outbox_events"].update_one(
                        {"external_reference_id": sg_id},
                        {
                            "$set": {
                                "delivery_status": event_name,
                                "delivery_updated_at": datetime.now(UTC),
                            }
                        },
                    )

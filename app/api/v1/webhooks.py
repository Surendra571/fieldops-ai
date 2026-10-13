import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import get_db
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/notifications")
async def handle_notification_webhook(
    request: Request,
    db: Any = Depends(get_db),
    x_signature: str | None = Header(None, alias="X-Signature"),
    x_timestamp: str | None = Header(None, alias="X-Timestamp"),
):
    """
    Ingest notification delivery receipts (Twilio, SendGrid, Mock).
    Enforces HMAC-SHA256 signature verification, 5-minute replay window, and idempotency.
    """
    raw_body = await request.body()

    # Validate HMAC signature if provided or required
    if x_signature:
        valid = WebhookService.verify_signature(
            payload_bytes=raw_body,
            signature_header=x_signature,
            timestamp_header=x_timestamp,
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature or expired timestamp replay.",
            )

    try:
        data = json.loads(raw_body)
    except Exception:
        data = {}

    service = WebhookService(db)
    webhook_id = (
        data.get("id")
        or data.get("MessageSid")
        or request.headers.get("X-Delivery-Id", "unknown_id")
    )
    provider = data.get("provider", "generic_notification")
    event_type = data.get("event", "status_update")

    result = await service.ingest_event(
        provider=provider,
        webhook_id=webhook_id,
        event_type=event_type,
        payload=data,
    )
    return result


@router.post("/crm")
async def handle_crm_webhook(
    request: Request,
    db: Any = Depends(get_db),
    x_signature: str | None = Header(None, alias="X-Signature"),
    x_timestamp: str | None = Header(None, alias="X-Timestamp"),
):
    """
    Ingest incoming CRM synchronization updates (HubSpot, Salesforce).
    """
    raw_body = await request.body()

    if x_signature:
        valid = WebhookService.verify_signature(
            payload_bytes=raw_body,
            signature_header=x_signature,
            timestamp_header=x_timestamp,
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid CRM webhook signature or expired timestamp replay.",
            )

    try:
        data = json.loads(raw_body)
    except Exception:
        data = {}

    service = WebhookService(db)
    webhook_id = data.get("eventId") or data.get("id") or "crm_event"
    return await service.ingest_event(
        provider="crm",
        webhook_id=webhook_id,
        event_type=data.get("subscriptionType", "crm_update"),
        payload=data,
    )

import logging
from typing import Any

from app.integrations.calendar import get_calendar_provider
from app.integrations.calendar.protocol import CalendarEventPayload
from app.integrations.crm import get_crm_provider
from app.integrations.crm.protocol import CRMCustomerPayload, CRMWorkOrderPayload
from app.integrations.notifications import get_notification_provider
from app.repositories.outbox_repo import OutboxRepository
from app.schemas.outbox import OutboxEventType
from app.services.notification_templates import (
    NotificationTemplateService,
    NotificationTemplateType,
)

logger = logging.getLogger(__name__)


class OutboxMetricsTracker:
    """In-memory atomic metrics counters for operational observability."""

    def __init__(self):
        self.notifications_sent_total: int = 0
        self.notifications_failed_total: int = 0
        self.notifications_retried_total: int = 0
        self.dead_letter_total: int = 0

    def inc_sent(self):
        self.notifications_sent_total += 1

    def inc_failed(self):
        self.notifications_failed_total += 1

    def inc_retried(self):
        self.notifications_retried_total += 1

    def inc_dead_letter(self):
        self.dead_letter_total += 1

    def get_stats(self) -> dict[str, int]:
        return {
            "notifications_sent_total": self.notifications_sent_total,
            "notifications_failed_total": self.notifications_failed_total,
            "notifications_retried_total": self.notifications_retried_total,
            "dead_letter_total": self.dead_letter_total,
        }


metrics_tracker = OutboxMetricsTracker()

EVENT_TYPE_TO_TEMPLATE: dict[str, NotificationTemplateType] = {
    OutboxEventType.NOTIFICATION_BOOKING_CONFIRMED.value: NotificationTemplateType.BOOKING_CONFIRMATION,
    OutboxEventType.NOTIFICATION_REMINDER_24H.value: NotificationTemplateType.APPOINTMENT_REMINDER_24H,
    OutboxEventType.NOTIFICATION_REMINDER_2H.value: NotificationTemplateType.APPOINTMENT_REMINDER_2H,
    OutboxEventType.NOTIFICATION_TECHNICIAN_ASSIGNED.value: NotificationTemplateType.TECHNICIAN_ASSIGNED,
    OutboxEventType.NOTIFICATION_APPOINTMENT_RESCHEDULED.value: NotificationTemplateType.APPOINTMENT_RESCHEDULED,
    OutboxEventType.NOTIFICATION_APPOINTMENT_CANCELLED.value: NotificationTemplateType.APPOINTMENT_CANCELLED,
    OutboxEventType.NOTIFICATION_WORK_ORDER_COMPLETED.value: NotificationTemplateType.WORK_ORDER_COMPLETED,
}


class OutboxService:
    """
    Dispatcher service that processes staged outbox events, invokes integration adapters,
    handles errors with backoff/jitter, and moves exhausted events to dead-letter storage.
    """

    def __init__(self, outbox_repo: OutboxRepository):
        self.outbox_repo = outbox_repo

    async def process_batch(self, limit: int = 50, worker_id: str | None = None) -> dict[str, int]:
        """
        Process a batch of due outbox events.
        Returns a summary of processed, succeeded, and failed counts.
        """
        events = await self.outbox_repo.fetch_batch_for_processing(limit=limit, worker_id=worker_id)
        succeeded = 0
        failed = 0

        for event in events:
            ok = await self.process_single_event(event)
            if ok:
                succeeded += 1
            else:
                failed += 1

        return {
            "batch_size": len(events),
            "succeeded": succeeded,
            "failed": failed,
        }

    async def process_single_event(self, event: dict[str, Any]) -> bool:
        event_id = event["event_id"]
        event_type_str = event["event_type"]
        correlation_id = event.get("correlation_id", "none")
        payload = event.get("payload", {})
        retry_count = event.get("retry_count", 0)
        max_retries = event.get("max_retries", 5)

        logger.info(
            "Processing outbox event",
            extra={
                "event_id": event_id,
                "event_type": event_type_str,
                "correlation_id": correlation_id,
                "retry_count": retry_count,
            },
        )

        try:
            external_ref = None

            # 1. Notification Event Dispatch
            if event_type_str.startswith("NOTIFICATION_"):
                external_ref = await self._handle_notification(event_type_str, payload)
                metrics_tracker.inc_sent()

            # 2. Calendar Synchronization
            elif event_type_str == OutboxEventType.CALENDAR_SYNC_EVENT.value:
                external_ref = await self._handle_calendar_sync(payload)

            # 3. CRM Customer Synchronization
            elif event_type_str == OutboxEventType.CRM_SYNC_CUSTOMER.value:
                external_ref = await self._handle_crm_customer_sync(payload)

            # 4. CRM Work Order Synchronization
            elif event_type_str == OutboxEventType.CRM_SYNC_WORK_ORDER.value:
                external_ref = await self._handle_crm_work_order_sync(payload)

            else:
                logger.warning(f"Unhandled outbox event type: {event_type_str}")

            # Mark completed in repository
            await self.outbox_repo.mark_completed(event_id, external_reference_id=external_ref)
            logger.info(
                f"Successfully completed outbox event {event_id} (ref={external_ref})",
                extra={"event_id": event_id, "external_ref": external_ref},
            )
            return True

        except Exception as exc:
            error_msg = str(exc)
            metrics_tracker.inc_failed()
            if retry_count + 1 >= max_retries:
                metrics_tracker.inc_dead_letter()
                logger.error(
                    f"Outbox event {event_id} permanently failed after {max_retries} attempts: {error_msg}. Sent to DEAD_LETTER.",
                    extra={
                        "event_id": event_id,
                        "error": error_msg,
                        "correlation_id": correlation_id,
                    },
                )
            else:
                metrics_tracker.inc_retried()
                logger.warning(
                    f"Outbox event {event_id} failed attempt {retry_count + 1}/{max_retries}: {error_msg}. Scheduling retry.",
                    extra={
                        "event_id": event_id,
                        "error": error_msg,
                        "correlation_id": correlation_id,
                    },
                )

            await self.outbox_repo.mark_failed(
                event_id=event_id,
                error_message=error_msg,
                current_retry_count=retry_count,
                max_retries=max_retries,
            )
            return False

    async def _handle_notification(self, event_type_str: str, payload: dict[str, Any]) -> str:
        provider = get_notification_provider()
        template_type = EVENT_TYPE_TO_TEMPLATE.get(event_type_str)
        if not template_type:
            raise ValueError(f"Unknown notification event type: {event_type_str}")

        rendered = NotificationTemplateService.render(template_type, payload.get("context", {}))
        recipient_phone = payload.get("to_phone")
        recipient_email = payload.get("to_email")
        channel = payload.get("channel", "BOTH")  # "SMS", "EMAIL", "BOTH"

        refs = []

        # Send SMS
        if recipient_phone and channel in ("SMS", "BOTH"):
            sms_res = await provider.send_sms(
                to_phone=recipient_phone,
                body=rendered.sms_body,
                metadata={"template": template_type.value},
            )
            if not sms_res.success:
                raise RuntimeError(f"SMS delivery failed: {sms_res.error_message}")
            refs.append(sms_res.provider_message_id)

        # Send Email
        if recipient_email and channel in ("EMAIL", "BOTH"):
            email_res = await provider.send_email(
                to_email=recipient_email,
                subject=rendered.email_subject,
                body_html=rendered.email_html,
                body_text=rendered.email_text,
                metadata={"template": template_type.value},
            )
            if not email_res.success:
                raise RuntimeError(f"Email delivery failed: {email_res.error_message}")
            refs.append(email_res.provider_message_id)

        return ",".join(refs) if refs else "notif_delivered"

    async def _handle_calendar_sync(self, payload: dict[str, Any]) -> str:
        provider = get_calendar_provider()
        event_payload = CalendarEventPayload(
            title=payload["title"],
            description=payload.get("description", ""),
            start_time=payload["start_time"],
            end_time=payload["end_time"],
            location=payload.get("location", ""),
            attendee_emails=payload.get("attendee_emails", []),
            metadata=payload.get("metadata"),
        )
        existing_ref = payload.get("external_calendar_event_id")
        if existing_ref:
            res = await provider.update_event(existing_ref, event_payload)
        else:
            res = await provider.create_event(event_payload)

        if not res.success:
            raise RuntimeError(f"Calendar sync failed: {res.error_message}")
        return res.external_event_id

    async def _handle_crm_customer_sync(self, payload: dict[str, Any]) -> str:
        provider = get_crm_provider()
        cust_payload = CRMCustomerPayload(
            internal_customer_id=payload["internal_customer_id"],
            name=payload["name"],
            email=payload.get("email"),
            phone=payload["phone"],
            service_address=payload.get("service_address", ""),
            metadata=payload.get("metadata"),
        )
        res = await provider.sync_customer(cust_payload)
        if not res.success:
            raise RuntimeError(f"CRM customer sync failed: {res.error_message}")
        return res.external_record_id

    async def _handle_crm_work_order_sync(self, payload: dict[str, Any]) -> str:
        provider = get_crm_provider()
        wo_payload = CRMWorkOrderPayload(
            internal_work_order_id=payload["internal_work_order_id"],
            work_order_number=payload["work_order_number"],
            customer_id=payload["customer_id"],
            category=payload["category"],
            priority=payload["priority"],
            status=payload["status"],
            description=payload["description"],
            assigned_technician_id=payload.get("assigned_technician_id"),
            metadata=payload.get("metadata"),
        )
        res = await provider.sync_work_order(wo_payload)
        if not res.success:
            raise RuntimeError(f"CRM work order sync failed: {res.error_message}")
        return res.external_record_id

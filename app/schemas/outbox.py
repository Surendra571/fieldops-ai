from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutboxEventStatus(str, Enum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    SENT = "SENT"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxEventType(str, Enum):
    NOTIFICATION_BOOKING_CONFIRMED = "NOTIFICATION_BOOKING_CONFIRMED"
    NOTIFICATION_REMINDER_24H = "NOTIFICATION_REMINDER_24H"
    NOTIFICATION_REMINDER_2H = "NOTIFICATION_REMINDER_2H"
    NOTIFICATION_TECHNICIAN_ASSIGNED = "NOTIFICATION_TECHNICIAN_ASSIGNED"
    NOTIFICATION_APPOINTMENT_RESCHEDULED = "NOTIFICATION_APPOINTMENT_RESCHEDULED"
    NOTIFICATION_APPOINTMENT_CANCELLED = "NOTIFICATION_APPOINTMENT_CANCELLED"
    NOTIFICATION_WORK_ORDER_COMPLETED = "NOTIFICATION_WORK_ORDER_COMPLETED"
    CALENDAR_SYNC_EVENT = "CALENDAR_SYNC_EVENT"
    CRM_SYNC_CUSTOMER = "CRM_SYNC_CUSTOMER"
    CRM_SYNC_WORK_ORDER = "CRM_SYNC_WORK_ORDER"


class OutboxEventCreate(BaseModel):
    event_type: OutboxEventType
    aggregate_type: str = Field(..., description="e.g. Appointment, WorkOrder, Customer")
    aggregate_id: str
    payload: dict[str, Any]
    correlation_id: str | None = None
    idempotency_key: str | None = None
    max_retries: int = 5


class OutboxEventResponse(BaseModel):
    id: str
    event_id: str
    event_type: OutboxEventType
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    status: OutboxEventStatus
    retry_count: int
    max_retries: int
    next_retry_at: datetime
    last_error: str | None = None
    external_reference_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class OutboxMetricsResponse(BaseModel):
    total_events: int
    pending: int
    in_flight: int
    sent: int
    failed: int
    dead_letter: int
    notifications_sent_total: int
    notifications_failed_total: int
    notifications_retried_total: int

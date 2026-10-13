from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class AppointmentStatus(str, Enum):
    TENTATIVE_HOLD = "TENTATIVE_HOLD"
    CONFIRMED = "CONFIRMED"
    EN_ROUTE = "EN_ROUTE"
    ON_SITE = "ON_SITE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class AppointmentBase(BaseModel):
    work_order_id: str
    technician_id: str
    customer_id: str
    scheduled_start: datetime
    scheduled_end: datetime
    customer_notes: str | None = None
    technician_notes: str | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "AppointmentBase":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        return self


class AppointmentCreate(AppointmentBase):
    reservation_token: str | None = None
    status: AppointmentStatus = AppointmentStatus.CONFIRMED


class AppointmentUpdate(BaseModel):
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    technician_id: str | None = None
    customer_notes: str | None = None
    technician_notes: str | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "AppointmentUpdate":
        if self.scheduled_start and self.scheduled_end:
            if self.scheduled_end <= self.scheduled_start:
                raise ValueError("scheduled_end must be after scheduled_start")
        return self


class AppointmentStatusUpdate(BaseModel):
    new_status: AppointmentStatus
    reason: str | None = None
    actor_id: str | None = None


class AppointmentResponse(AppointmentBase):
    id: str
    appointment_number: str
    status: AppointmentStatus
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    lock_version: int = 1
    reservation_token: str | None = None
    missed_appointment_risk_score: float | None = None
    created_at: datetime
    updated_at: datetime


# --- Slot Discovery & Hold Models ---


class SlotOption(BaseModel):
    start_time: datetime
    end_time: datetime
    technician_id: str
    technician_name: str
    formatted_time_window: str


class AvailableSlotsRequest(BaseModel):
    technician_id: str | None = None
    work_order_id: str | None = None
    target_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    duration_minutes: int = Field(default=60, ge=15, le=480)
    buffer_minutes: int = Field(default=30, ge=0, le=120)
    timezone: str = "America/New_York"


class AvailableSlotsResponse(BaseModel):
    target_date: str
    timezone: str
    slots: list[SlotOption]


class HoldSlotRequest(BaseModel):
    technician_id: str
    work_order_id: str
    scheduled_start: datetime
    scheduled_end: datetime
    customer_id: str

    @model_validator(mode="after")
    def validate_hold_times(self) -> "HoldSlotRequest":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        return self


class HoldSlotResponse(BaseModel):
    reservation_token: str
    technician_id: str
    work_order_id: str
    scheduled_start: datetime
    scheduled_end: datetime
    expires_at: datetime
    status: str = "TENTATIVE_HOLD"


class ConfirmBookingRequest(BaseModel):
    reservation_token: str
    user_confirmed: bool = Field(..., description="Explicit confirmation required to book")
    customer_notes: str | None = None
    idempotency_key: str | None = None


class CancelAppointmentRequest(BaseModel):
    reason: str = Field(..., min_length=3)
    actor_id: str | None = None


class RescheduleAppointmentRequest(BaseModel):
    new_scheduled_start: datetime
    new_scheduled_end: datetime
    technician_id: str | None = None
    reason: str | None = None
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def validate_reschedule_times(self) -> "RescheduleAppointmentRequest":
        if self.new_scheduled_end <= self.new_scheduled_start:
            raise ValueError("new_scheduled_end must be after new_scheduled_start")
        return self

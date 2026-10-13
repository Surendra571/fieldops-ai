from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.customer import ServiceAddress


class WorkOrderCategory(str, Enum):
    HVAC = "HVAC"
    PLUMBING = "PLUMBING"
    ELECTRICAL = "ELECTRICAL"
    APPLIANCE = "APPLIANCE"
    ROOFING = "ROOFING"


class WorkOrderPriority(str, Enum):
    EMERGENCY = "EMERGENCY"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    ROUTINE = "ROUTINE"


class WorkOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    TRIAGED = "TRIAGED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class WorkOrderSource(str, Enum):
    VOICE = "VOICE"
    CHAT = "CHAT"
    WEB = "WEB"
    MANUAL = "MANUAL"


class TimeOfDayPreference(str, Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"
    ANYTIME = "ANYTIME"


class PreferredTimeWindow(BaseModel):
    preferred_date: str | None = Field(
        None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD"
    )
    time_of_day: TimeOfDayPreference = TimeOfDayPreference.ANYTIME
    specific_start: datetime | None = None
    specific_end: datetime | None = None


class AuditTransition(BaseModel):
    transition_id: str
    from_status: str
    to_status: str
    actor: str
    timestamp: datetime
    reason: str | None = None


class WorkOrderBase(BaseModel):
    customer_id: str
    category: WorkOrderCategory
    priority: WorkOrderPriority = WorkOrderPriority.MEDIUM
    urgency: WorkOrderPriority | None = None
    description: str = Field(..., min_length=5)
    symptoms: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    service_address: ServiceAddress
    preferred_time_window: PreferredTimeWindow | None = None
    source: WorkOrderSource = WorkOrderSource.MANUAL

    @model_validator(mode="after")
    def sync_urgency_and_priority(self) -> "WorkOrderBase":
        if self.urgency is not None and self.priority == WorkOrderPriority.MEDIUM:
            self.priority = self.urgency
        elif self.urgency is None:
            self.urgency = self.priority
        return self


class WorkOrderCreate(WorkOrderBase):
    idempotency_key: str | None = None
    estimated_duration_minutes: int | None = Field(default=60, ge=15, le=480)
    assigned_technician_id: str | None = None


class WorkOrderUpdate(BaseModel):
    category: WorkOrderCategory | None = None
    priority: WorkOrderPriority | None = None
    urgency: WorkOrderPriority | None = None
    description: str | None = None
    symptoms: list[str] | None = None
    required_skills: list[str] | None = None
    service_address: ServiceAddress | None = None
    preferred_time_window: PreferredTimeWindow | None = None
    estimated_duration_minutes: int | None = None
    assigned_technician_id: str | None = None

    @model_validator(mode="after")
    def sync_urgency(self) -> "WorkOrderUpdate":
        if self.urgency is not None and self.priority is None:
            self.priority = self.urgency
        return self


class WorkOrderStatusUpdate(BaseModel):
    new_status: WorkOrderStatus
    reason: str | None = None
    actor_id: str | None = None


class WorkOrderResponse(WorkOrderBase):
    id: str
    work_order_number: str
    status: WorkOrderStatus
    idempotency_key: str | None = None
    estimated_duration_minutes: int
    predicted_by_ml: bool = False
    assigned_technician_id: str | None = None
    active_appointment_id: str | None = None
    ai_confidence_score: float | None = None
    audit_trail: list[AuditTransition] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

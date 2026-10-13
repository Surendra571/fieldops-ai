from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class FieldConfidence(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNCERTAIN = "uncertain"
    MISSING = "missing"


class EscalationReason(str, Enum):
    CUSTOMER_REQUEST = "customer_requested_human"
    COMPLEX_REQUEST = "complex_out_of_scope_request"
    MULTIPLE_REPAIR_FAILURES = "repeated_validation_failures"
    POTENTIAL_SAFETY_HAZARD = "critical_hazard_emergency"
    PROMPT_INJECTION_DETECTED = "security_prompt_injection"
    SYSTEM_OUTAGE = "downstream_provider_outage"


class ExtractedField(BaseModel, Generic[T]):
    value: T | None = None
    confidence: FieldConfidence = FieldConfidence.MISSING
    raw_text: str | None = None


class ExtractedWorkOrderDraft(BaseModel):
    customer_name: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    customer_phone: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    customer_email: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    service_address: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    issue_category: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    issue_description: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    urgency: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    equipment_type: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    preferred_window: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    required_skills: ExtractedField[list[str]] = Field(
        default_factory=lambda: ExtractedField[list[str]]()
    )

    completeness_score: float = 0.0
    missing_required_fields: list[str] = Field(default_factory=list)
    is_ready_for_dispatch: bool = False


class ConversationMessage(BaseModel):
    id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ConversationSessionRead(BaseModel):
    id: str
    session_id: str
    customer_id: str | None = None
    work_order_id: str | None = None
    tentative_hold_id: str | None = None
    status: str = "active"  # "active", "escalated", "completed", "expired"
    extracted_draft: ExtractedWorkOrderDraft | None = None
    history: list[ConversationMessage] = Field(default_factory=list)
    escalation_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentChatRequest(BaseModel):
    session_id: str | None = None
    customer_id: str | None = None
    session_token: str | None = None
    message: str = Field(..., min_length=1, max_length=4000)


class AgentChatResponse(BaseModel):
    session_id: str
    session_token: str | None = None
    reply: str
    extracted_draft: ExtractedWorkOrderDraft | None = None
    tools_invoked: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    pending_action: dict[str, Any] | None = None
    is_escalated: bool = False
    escalation_reason: str | None = None


class AgentVoiceRequest(BaseModel):
    session_id: str | None = None
    customer_id: str | None = None
    session_token: str | None = None
    audio_base64: str = Field(..., description="Base64 encoded audio bytes")
    audio_format: str = Field("wav", description="Audio format (wav, mp3, webm)")


class AgentVoiceResponse(BaseModel):
    session_id: str
    session_token: str | None = None
    user_transcript: str
    reply_text: str
    reply_audio_base64: str
    extracted_draft: ExtractedWorkOrderDraft | None = None
    tools_invoked: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    is_escalated: bool = False
    escalation_reason: str | None = None

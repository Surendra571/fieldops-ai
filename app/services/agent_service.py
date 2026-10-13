import base64
import json
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from app.agent.tools import AgentToolRegistry
from app.core.config import settings
from app.integrations.llm.protocol import ChatMessage, LLMProviderProtocol, ToolCall
from app.integrations.voice.protocol import AudioPayload, SpeechToTextProtocol, TextToSpeechProtocol
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.agent import (
    AgentChatResponse,
    AgentVoiceResponse,
    EscalationReason,
    ExtractedField,
    ExtractedWorkOrderDraft,
    FieldConfidence,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are FieldOps AI, a polite, professional, and efficient voice and text assistant for field service scheduling and dispatch.
Your duties:
1. Help customers report repair and maintenance issues for HVAC, Plumbing, Electrical, Appliances, and Roofing.
2. Accurately capture their issue description, urgency, and exact service street address.
3. NEVER hallucinate or assume addresses, customer names, or phone numbers. If an address or required detail is missing, ask a brief, polite follow-up question.
4. When all required information is provided, invoke the `create_service_request` tool.
5. Offer available appointment slots using `get_available_slots`.
6. When a customer wants a slot, use `propose_appointment_hold` to place a temporary hold.
7. CRITICAL RULE: Never finalize a booking or rescheduling without explicit customer confirmation. Only call `confirm_booking` when the customer has clearly confirmed (e.g., 'yes', 'confirm', 'please book').
8. If the customer is facing an emergency (e.g. active gas leak, sparking electrical fire, major flooding) or asks for a human, immediately call `escalate_to_human`.
9. Keep responses concise, clear, and natural for voice conversation (1-3 sentences).
"""


class AgentService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        tool_registry: AgentToolRegistry,
        llm_adapter: LLMProviderProtocol,
        stt_adapter: SpeechToTextProtocol,
        tts_adapter: TextToSpeechProtocol,
    ):
        self.conversation_repo = conversation_repo
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.stt_adapter = stt_adapter
        self.tts_adapter = tts_adapter

    def _detect_prompt_injection(self, text: str) -> bool:
        if not settings.PROMPT_INJECTION_STRICT_MODE:
            return False
        patterns = [
            r"ignore (all )?(previous|above|system) instructions",
            r"reveal (system|hidden) prompt",
            r"system instructions",
            r"system message",
            r"jailbreak",
            r"dan mode",
            r"override safety rules",
            r"you are now in developer mode",
        ]
        return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)

    def _extract_work_order_draft(
        self, history: list[dict[str, Any]], current_draft: dict[str, Any] | None = None
    ) -> ExtractedWorkOrderDraft:
        """
        Deterministically extracts and tracks work order draft fields with explicit confidence levels.
        """
        user_texts = [
            m.get("content", "") for m in history if m.get("role") == "user" and m.get("content")
        ]
        combined_text = " ".join(user_texts).strip()

        draft = ExtractedWorkOrderDraft()

        # Customer Name
        name_match = re.search(
            r"(?:my name is|this is|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            combined_text,
            re.IGNORECASE,
        )
        if name_match:
            draft.customer_name = ExtractedField[str](
                value=name_match.group(1).strip(),
                confidence=FieldConfidence.VERIFIED,
                raw_text=name_match.group(0),
            )
        elif current_draft and current_draft.get("customer_name", {}).get("value"):
            draft.customer_name = ExtractedField[str](**current_draft["customer_name"])

        # Phone
        phone_match = re.search(
            r"(\+?[0-9]{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", combined_text
        )
        if phone_match:
            draft.customer_phone = ExtractedField[str](
                value=phone_match.group(0).strip(),
                confidence=FieldConfidence.VERIFIED,
                raw_text=phone_match.group(0),
            )
        elif current_draft and current_draft.get("customer_phone", {}).get("value"):
            draft.customer_phone = ExtractedField[str](**current_draft["customer_phone"])

        # Service Address
        addr_match = re.search(
            r"(?:at|address(?:\s+is)?)\s+([0-9]+\s+[A-Za-z0-9\s,\.]+?(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Boulevard|Blvd|Terrace|Way|Court|Ct)[A-Za-z0-9\s,\.]*)",
            combined_text,
            re.IGNORECASE,
        )
        if not addr_match:
            addr_match = re.search(
                r"([0-9]{2,5}\s+[A-Za-z0-9\s,\.]+(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Boulevard|Blvd|Terrace|Way|Court|Ct))",
                combined_text,
                re.IGNORECASE,
            )
        if addr_match:
            draft.service_address = ExtractedField[str](
                value=addr_match.group(1).strip(),
                confidence=FieldConfidence.VERIFIED,
                raw_text=addr_match.group(0),
            )
        elif current_draft and current_draft.get("service_address", {}).get("value"):
            draft.service_address = ExtractedField[str](**current_draft["service_address"])

        # Issue Category
        cat = None
        if re.search(
            r"(\bac\b|heat|cooling|furnace|air condition|hvac|thermostat)",
            combined_text,
            re.IGNORECASE,
        ):
            cat = "hvac"
        elif re.search(r"(roof|shingle|gutter)", combined_text, re.IGNORECASE):
            cat = "roofing"
        elif re.search(
            r"(appliance|fridge|refrigerator|washer|dryer|dishwasher|oven)",
            combined_text,
            re.IGNORECASE,
        ):
            cat = "appliance"
        elif re.search(
            r"(electric|power|outlet|circuit|breaker|light)", combined_text, re.IGNORECASE
        ):
            cat = "electrical"
        elif re.search(
            r"(pipe|sink|drain|toilet|faucet|plumb|sewer|leak|water)", combined_text, re.IGNORECASE
        ):
            cat = "plumbing"

        if cat:
            draft.issue_category = ExtractedField[str](
                value=cat,
                confidence=FieldConfidence.VERIFIED,
                raw_text=cat,
            )
        elif current_draft and current_draft.get("issue_category", {}).get("value"):
            draft.issue_category = ExtractedField[str](**current_draft["issue_category"])

        # Issue Description
        if user_texts:
            draft.issue_description = ExtractedField[str](
                value=user_texts[-1],
                confidence=FieldConfidence.VERIFIED,
                raw_text=user_texts[-1],
            )

        # Urgency
        urgency = "medium"
        if re.search(
            r"(emergency|flood|sparking|burst|smoke|urgent|critical|immediately)",
            combined_text,
            re.IGNORECASE,
        ):
            urgency = "critical"
        elif re.search(r"(soon|today|asap|high)", combined_text, re.IGNORECASE):
            urgency = "high"
        draft.urgency = ExtractedField[str](
            value=urgency,
            confidence=FieldConfidence.VERIFIED,
            raw_text=urgency,
        )

        # Calculate completeness & missing fields
        required_fields = {
            "customer_name": draft.customer_name.value,
            "customer_phone": draft.customer_phone.value,
            "service_address": draft.service_address.value,
            "issue_category": draft.issue_category.value,
            "issue_description": draft.issue_description.value,
        }

        missing = [f for f, val in required_fields.items() if not val]
        draft.missing_required_fields = missing
        completed_count = len(required_fields) - len(missing)
        draft.completeness_score = round(completed_count / len(required_fields), 2)
        draft.is_ready_for_dispatch = len(missing) == 0

        return draft

    async def process_chat(
        self,
        session_id: str | None,
        customer_id: str | None,
        user_message: str,
        session_token: str | None = None,
    ) -> AgentChatResponse:
        session = None
        if session_id:
            session = await self.conversation_repo.get_by_session_id(session_id)

        if not session:
            session_id = session_id or f"sess_{secrets.token_urlsafe(24)}"
            session_token = session_token or secrets.token_urlsafe(32)
            session = await self.conversation_repo.create_session(
                session_id=session_id,
                customer_id=customer_id,
                session_token=session_token,
            )
        else:
            existing_token = session.get("session_token")
            if (
                existing_token
                and session_token
                and not secrets.compare_digest(session_token, existing_token)
            ):
                from app.core.exceptions import ValidationException

                raise ValidationException("Invalid session_token for existing session.")
            session_token = existing_token or session_token or secrets.token_urlsafe(32)
            if not existing_token and session_token:
                await self.conversation_repo.update_session_state(
                    session_id, {"session_token": session_token}
                )

        # Prompt Injection check
        if self._detect_prompt_injection(user_message):
            reply = "I cannot fulfill this request. I am FieldOps AI, dedicated to assisting with field service and maintenance. How can I assist you with your equipment?"
            await self.conversation_repo.append_messages(
                session_id=session_id,
                new_messages=[
                    {
                        "id": str(uuid.uuid4()),
                        "role": "user",
                        "content": user_message,
                        "timestamp": datetime.now(UTC),
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "role": "assistant",
                        "content": reply,
                        "timestamp": datetime.now(UTC),
                    },
                ],
                status="active",
                escalation_reason=EscalationReason.PROMPT_INJECTION_DETECTED.value,
            )
            return AgentChatResponse(
                session_id=session_id,
                session_token=session_token,
                reply=reply,
                is_escalated=False,
                escalation_reason=EscalationReason.PROMPT_INJECTION_DETECTED.value,
            )

        # Append incoming user message to local history
        user_msg_doc = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now(UTC),
        }
        history = list(session.get("history", []))
        history.append(user_msg_doc)

        # Extract draft
        extracted_draft = self._extract_work_order_draft(history, session.get("extracted_draft"))

        # Build LLM Messages
        llm_messages: list[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
        ]
        # Include bounded conversation history
        for m in history[-settings.CONVERSATION_HISTORY_LIMIT :]:
            llm_messages.append(
                ChatMessage(
                    role=m["role"],
                    content=m.get("content"),
                    name=m.get("name"),
                    tool_call_id=m.get("tool_call_id"),
                    tool_calls=[
                        ToolCall(id=tc["id"], name=tc["name"], arguments=tc.get("arguments", {}))
                        for tc in (m.get("tool_calls") or [])
                    ],
                )
            )

        tools = self.tool_registry.get_definitions()
        tools_invoked: list[str] = []
        new_history_messages: list[dict[str, Any]] = [user_msg_doc]

        work_order_id = session.get("work_order_id")
        tentative_hold_id = session.get("tentative_hold_id")
        is_escalated = session.get("status") == "escalated"
        escalation_reason = session.get("escalation_reason")
        requires_confirmation = False
        pending_action = None

        # Multi-turn tool execution loop (bounded by AGENT_MAX_REPAIR_ATTEMPTS)
        for _ in range(settings.AGENT_MAX_REPAIR_ATTEMPTS):
            llm_res = await self.llm_adapter.generate(
                messages=llm_messages,
                tools=tools,
                temperature=0.0,
            )

            if not llm_res.tool_calls:
                # Normal text response
                reply_text = llm_res.content or "How else can I assist you with your service today?"
                assistant_msg_doc = {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": reply_text,
                    "timestamp": datetime.now(UTC),
                }
                new_history_messages.append(assistant_msg_doc)
                break

            # Handle tool calls
            assistant_tool_doc = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": llm_res.content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in llm_res.tool_calls
                ],
                "timestamp": datetime.now(UTC),
            }
            new_history_messages.append(assistant_tool_doc)
            llm_messages.append(
                ChatMessage(
                    role="assistant",
                    content=llm_res.content,
                    tool_calls=llm_res.tool_calls,
                )
            )

            for tc in llm_res.tool_calls:
                tools_invoked.append(tc.name)
                # Pass context
                ctx = {
                    "session_id": session_id,
                    "customer_id": session.get("customer_id"),
                    "work_order_id": work_order_id,
                    "tentative_hold_id": tentative_hold_id,
                }
                tool_result = await self.tool_registry.execute(tc.name, tc.arguments, ctx)

                if tc.name == "create_service_request" and tool_result.get("success"):
                    work_order_id = tool_result.get("work_order_id")

                if tc.name == "propose_appointment_hold" and tool_result.get("success"):
                    tentative_hold_id = tool_result.get("reservation_token")
                    requires_confirmation = True
                    pending_action = {
                        "action": "confirm_booking",
                        "hold_id": tentative_hold_id,
                    }

                if tc.name == "escalate_to_human":
                    is_escalated = True
                    escalation_reason = tool_result.get(
                        "reason", EscalationReason.CUSTOMER_REQUEST.value
                    )

                # Append tool result to conversation history & LLM messages
                tool_msg_doc = {
                    "id": str(uuid.uuid4()),
                    "role": "tool",
                    "name": tc.name,
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, default=str),
                    "timestamp": datetime.now(UTC),
                }
                new_history_messages.append(tool_msg_doc)
                llm_messages.append(
                    ChatMessage(
                        role="tool",
                        name=tc.name,
                        tool_call_id=tc.id,
                        content=json.dumps(tool_result, default=str),
                    )
                )

        else:
            # Reached max turns fallback
            reply_text = "I'm processing your request. Please let me know if you would like me to finalize your appointment."
            new_history_messages.append(
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": reply_text,
                    "timestamp": datetime.now(UTC),
                }
            )

        # Persist session state and history
        status = "escalated" if is_escalated else "active"
        await self.conversation_repo.append_messages(
            session_id=session_id,
            new_messages=new_history_messages,
            draft_updates=extracted_draft.model_dump(),
            work_order_id=work_order_id,
            tentative_hold_id=tentative_hold_id,
            status=status,
            escalation_reason=escalation_reason,
        )

        final_reply = (
            new_history_messages[-1].get("content") or "Thank you for contacting FieldOps AI."
        )

        return AgentChatResponse(
            session_id=session_id,
            session_token=session_token,
            reply=final_reply,
            extracted_draft=extracted_draft,
            tools_invoked=tools_invoked,
            requires_confirmation=requires_confirmation,
            pending_action=pending_action,
            is_escalated=is_escalated,
            escalation_reason=escalation_reason,
        )

    async def process_voice(
        self,
        session_id: str | None,
        customer_id: str | None,
        audio_content: bytes,
        audio_format: str = "wav",
        session_token: str | None = None,
    ) -> AgentVoiceResponse:
        """
        Receives customer audio payload -> STT -> Agent Chat reasoning -> TTS -> Audio response.
        """
        # 1. Speech-to-Text
        stt_payload = AudioPayload(content=audio_content, format=audio_format)
        stt_res = await self.stt_adapter.transcribe(stt_payload)
        user_transcript = stt_res.text

        # 2. Process Chat
        chat_res = await self.process_chat(
            session_id=session_id,
            customer_id=customer_id,
            user_message=user_transcript,
            session_token=session_token,
        )

        # 3. Text-to-Speech
        tts_res = await self.tts_adapter.synthesize(chat_res.reply)
        audio_b64 = base64.b64encode(tts_res.audio_content).decode("ascii")

        return AgentVoiceResponse(
            session_id=chat_res.session_id,
            session_token=chat_res.session_token,
            user_transcript=user_transcript,
            reply_text=chat_res.reply,
            reply_audio_base64=audio_b64,
            extracted_draft=chat_res.extracted_draft,
            tools_invoked=chat_res.tools_invoked,
            requires_confirmation=chat_res.requires_confirmation,
            is_escalated=chat_res.is_escalated,
            escalation_reason=chat_res.escalation_reason,
        )

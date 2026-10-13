import re
from collections.abc import Callable
from typing import Any

from app.integrations.llm.protocol import (
    ChatMessage,
    LLMProviderProtocol,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)


class MockLLMAdapter(LLMProviderProtocol):
    """
    Deterministic Mock LLM Adapter capable of evaluating normal and edge cases offline.
    Uses rule-based extraction and tool invocation logic.
    """

    def __init__(self) -> None:
        self.call_history: list[list[ChatMessage]] = []
        self._custom_handlers: list[
            Callable[[list[ChatMessage], list[ToolDefinition] | None], LLMResponse | None]
        ] = []

    def add_handler(
        self,
        handler: Callable[[list[ChatMessage], list[ToolDefinition] | None], LLMResponse | None],
    ) -> None:
        self._custom_handlers.insert(0, handler)

    def clear_handlers(self) -> None:
        self._custom_handlers.clear()

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        self.call_history.append(messages)

        # Check custom registered handlers first
        for handler in self._custom_handlers:
            custom_res = handler(messages, tools)
            if custom_res is not None:
                return custom_res

        # If the last message is a tool result, synthesize customer-facing response
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.role == "tool":
            return self._synthesize_tool_result(messages, last_msg)

        # Extract user messages
        user_msgs = [m.content for m in messages if m.role == "user" and m.content]
        full_user_text = " ".join(user_msgs).strip()
        last_user_text = user_msgs[-1] if user_msgs else ""

        # 1. Prompt Injection Detection
        injection_patterns = [
            r"ignore (all )?previous instructions",
            r"reveal (system|hidden) prompt",
            r"system instructions",
            r"jailbreak",
            r"dan mode",
            r"override safety rules",
        ]
        for pattern in injection_patterns:
            if re.search(pattern, last_user_text, re.IGNORECASE):
                return LLMResponse(
                    content="I cannot fulfill this request. I am FieldOps AI, here to assist with field service and maintenance requests. How can I help you with your equipment or service today?",
                    finish_reason="stop",
                )

        # 2. Human Escalation Request
        escalate_patterns = [
            r"speak to (a )?(human|person|agent|representative|dispatcher)",
            r"transfer me",
            r"let me talk to someone",
            r"operator",
        ]
        for pattern in escalate_patterns:
            if re.search(pattern, last_user_text, re.IGNORECASE):
                if tools and any(t.name == "escalate_to_human" for t in tools):
                    return LLMResponse(
                        tool_calls=[
                            ToolCall(
                                id="call_esc_1",
                                name="escalate_to_human",
                                arguments={
                                    "reason": "customer_requested_human",
                                    "summary": f"Customer requested human representative: '{last_user_text}'",
                                },
                            )
                        ],
                        finish_reason="tool_calls",
                    )
                return LLMResponse(
                    content="I am transferring you to a human dispatcher who can assist you directly.",
                    finish_reason="stop",
                )

        # 3. Work Order Status Check
        wo_match = re.search(
            r"(?:status of|check status|tracking)\s*(?:work order|job|order|ticket)?\s*#?([A-Za-z0-9_-]{5,36})",
            last_user_text,
            re.IGNORECASE,
        )
        if wo_match:
            wo_id = wo_match.group(1).strip()
            if tools and any(t.name == "get_work_order_status" for t in tools):
                return LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="call_status_1",
                            name="get_work_order_status",
                            arguments={"work_order_id": wo_id},
                        )
                    ],
                    finish_reason="tool_calls",
                )

        # 4. Explicit Confirmation for Booking
        confirmation_patterns = [
            r"^(yes|yeah|sure|confirm|please book|book it|go ahead|book that slot)",
            r"(confirm the booking|confirm my appointment)",
        ]
        is_confirming = any(
            re.search(pat, last_user_text.strip(), re.IGNORECASE) for pat in confirmation_patterns
        )

        # Check if conversation already has an active work order
        has_work_order = any(
            "work_order_id" in (m.content or "") or "WO-" in (m.content or "") for m in messages
        )

        if is_confirming and tools and any(t.name == "confirm_booking" for t in tools):
            # Extract appointment or hold details if available from history
            hold_id = "mock_hold_123"
            for m in reversed(messages):
                if m.content and "hold_id" in m.content:
                    match = re.search(r"['\"]hold_id['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.content)
                    if match:
                        hold_id = match.group(1)
                        break

            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call_confirm_1",
                        name="confirm_booking",
                        arguments={
                            "hold_id": hold_id,
                            "user_confirmed": True,
                        },
                    )
                ],
                finish_reason="tool_calls",
            )

        # 5. Check Available Slots / Scheduling Inquiry
        slot_inquiry = re.search(
            r"(available slots?|when can (someone|technician) come|earliest (time|slot)|schedule|book an appointment)",
            last_user_text,
            re.IGNORECASE,
        )
        if slot_inquiry and tools and any(t.name == "get_available_slots" for t in tools):
            # Find work_order_id from messages if available
            wo_id = "default_wo"
            for m in reversed(messages):
                if m.content:
                    match = re.search(
                        r"['\"]work_order_id['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.content
                    ) or re.search(r"['\"]id['\"]\s*:\s*['\"]([0-9a-f]{24})['\"]", m.content)
                    if match:
                        wo_id = match.group(1)
                        break

            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call_slots_1",
                        name="get_available_slots",
                        arguments={
                            "work_order_id": wo_id,
                            "days_ahead": 3,
                        },
                    )
                ],
                finish_reason="tool_calls",
            )

        # 6. Service Request Extraction & Tool Calling
        # Categorize issue
        category = "general"
        if re.search(
            r"(\bac\b|heat|cooling|furnace|air condition|hvac|thermostat)",
            full_user_text,
            re.IGNORECASE,
        ):
            category = "hvac"
        elif re.search(r"(roof|shingle|gutter)", full_user_text, re.IGNORECASE):
            category = "roofing"
        elif re.search(
            r"(appliance|fridge|refrigerator|washer|dryer|dishwasher|oven)",
            full_user_text,
            re.IGNORECASE,
        ):
            category = "appliance"
        elif re.search(
            r"(electric|power|outlet|circuit|breaker|light)", full_user_text, re.IGNORECASE
        ):
            category = "electrical"
        elif re.search(
            r"(pipe|sink|drain|toilet|faucet|plumb|sewer|leak|water)", full_user_text, re.IGNORECASE
        ):
            category = "plumbing"

        # Urgency
        urgency = "medium"
        if re.search(
            r"(emergency|flood|sparking|burst|smoke|urgent|critical|immediately)",
            full_user_text,
            re.IGNORECASE,
        ):
            urgency = "critical"
        elif re.search(r"(soon|today|asap|high)", full_user_text, re.IGNORECASE):
            urgency = "high"

        # Address Extraction
        # Look for numbers followed by street/ave/blvd/dr/road/lane/st or explicit "at <address>"
        address = None
        addr_match = re.search(
            r"(?:at|address(?:\s+is)?)\s+([0-9]+\s+[A-Za-z0-9\s,\.]+?(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Boulevard|Blvd|Terrace|Way|Court|Ct)[A-Za-z0-9\s,\.]*)",
            full_user_text,
            re.IGNORECASE,
        )
        if not addr_match:
            addr_match = re.search(
                r"([0-9]{2,5}\s+[A-Za-z0-9\s,\.]+(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Boulevard|Blvd|Terrace|Way|Court|Ct))",
                full_user_text,
                re.IGNORECASE,
            )
        if addr_match:
            address = addr_match.group(1).strip()

        # Customer name & contact extraction
        name = "Valued Customer"
        name_match = re.search(
            r"(?:my name is|this is|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            full_user_text,
            re.IGNORECASE,
        )
        if name_match:
            name = name_match.group(1).strip()

        phone = None
        phone_match = re.search(
            r"(\+?[0-9]{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", full_user_text
        )
        if phone_match:
            phone = phone_match.group(0).strip()

        # Check required fields completeness
        is_issue_stated = bool(
            re.search(
                r"(leak|broken|not working|repair|service|maintenance|fix|problem|issue|burst|smoke|drain|clog|cold|heat|furnace|panel|spark|smell|won't|stopped|fail|warm|noise)",
                full_user_text,
                re.IGNORECASE,
            )
        )

        # If user is describing an issue but hasn't provided address yet:
        if is_issue_stated and not address:
            return LLMResponse(
                content="I understand you're having an issue with your equipment. Could you please provide the exact service address where the technician should be dispatched?",
                finish_reason="stop",
            )

        # If user provided issue and address, invoke create_service_request
        if (
            is_issue_stated
            and address
            and tools
            and any(t.name == "create_service_request" for t in tools)
            and not has_work_order
        ):
            issue_desc = (
                last_user_text
                if bool(
                    re.search(
                        r"(leak|broken|repair|fix|problem|issue|drain|clog|smoke|fail|won't|warm)",
                        last_user_text,
                        re.IGNORECASE,
                    )
                )
                else full_user_text
            )
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call_create_wo_1",
                        name="create_service_request",
                        arguments={
                            "customer_name": name,
                            "customer_phone": phone or "+15551234567",
                            "address": address,
                            "issue_category": category,
                            "issue_description": issue_desc,
                            "urgency": urgency,
                        },
                    )
                ],
                finish_reason="tool_calls",
            )

        # Fallback friendly response
        return LLMResponse(
            content="Hello! I'm FieldOps AI. How can I help you with your HVAC, plumbing, or electrical service today?",
            finish_reason="stop",
        )

    def _synthesize_tool_result(
        self, messages: list[ChatMessage], tool_msg: ChatMessage
    ) -> LLMResponse:
        content = tool_msg.content or ""
        name = tool_msg.name or ""

        if name == "create_service_request":
            return LLMResponse(
                content=f"I have created your service work order ({content}). Would you like me to find the earliest available appointment slots for you?",
                finish_reason="stop",
            )
        elif name == "get_available_slots":
            return LLMResponse(
                content=f"Here are the available technician slots: {content}. Would you like me to hold one of these slots for you?",
                finish_reason="stop",
            )
        elif name == "propose_appointment_hold":
            return LLMResponse(
                content=f"I have placed a 15-minute temporary hold on that slot ({content}). Please reply 'confirm' if you would like me to finalize this appointment.",
                finish_reason="stop",
            )
        elif name == "confirm_booking":
            return LLMResponse(
                content=f"Great news! Your appointment has been officially confirmed: {content}. Our technician will see you then!",
                finish_reason="stop",
            )
        elif name == "escalate_to_human":
            return LLMResponse(
                content=f"I have escalated your request to our senior dispatch team ({content}). A human specialist is reviewing your case and will follow up shortly.",
                finish_reason="stop",
            )
        elif name == "get_work_order_status":
            return LLMResponse(
                content=f"Here is the current status of your request: {content}.",
                finish_reason="stop",
            )

        return LLMResponse(
            content=f"The operation completed successfully: {content}. Is there anything else I can assist you with?",
            finish_reason="stop",
        )

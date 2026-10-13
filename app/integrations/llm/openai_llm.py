import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.llm.protocol import (
    ChatMessage,
    LLMProviderProtocol,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class OpenAILLMAdapter(LLMProviderProtocol):
    """
    OpenAI Chat Completions adapter with tool calling and structured outputs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_url: str = "https://api.openai.com/v1/chat/completions",
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.api_url = api_url

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured for OpenAILLMAdapter.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Format messages for OpenAI API
        formatted_messages: list[dict[str, Any]] = []
        for m in messages:
            msg_dict: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                msg_dict["content"] = m.content
            if m.name:
                msg_dict["name"] = m.name
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                            if isinstance(tc.arguments, dict)
                            else str(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
            formatted_messages.append(msg_dict)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=settings.AGENT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            choice_msg = choice["message"]
            content = choice_msg.get("content")
            finish_reason = choice.get("finish_reason", "stop")

            parsed_tool_calls: list[ToolCall] = []
            if "tool_calls" in choice_msg and choice_msg["tool_calls"]:
                for tc in choice_msg["tool_calls"]:
                    call_id = tc["id"]
                    func = tc["function"]
                    func_name = func["name"]
                    args_str = func["arguments"]
                    try:
                        args = json.loads(args_str)
                    except Exception:
                        args = {"raw_args": args_str}

                    parsed_tool_calls.append(ToolCall(id=call_id, name=func_name, arguments=args))

            usage = data.get("usage", {})

            return LLMResponse(
                content=content,
                tool_calls=parsed_tool_calls,
                finish_reason=finish_reason,
                usage=usage,
                raw_response=data,
            )

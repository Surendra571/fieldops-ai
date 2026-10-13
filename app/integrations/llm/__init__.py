from app.core.config import settings
from app.integrations.llm.mock_llm import MockLLMAdapter
from app.integrations.llm.openai_llm import OpenAILLMAdapter
from app.integrations.llm.protocol import (
    ChatMessage,
    LLMProviderProtocol,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)

_llm_adapter_instance: LLMProviderProtocol | None = None


def get_llm_adapter() -> LLMProviderProtocol:
    global _llm_adapter_instance
    if _llm_adapter_instance is None:
        if settings.LLM_PROVIDER == "openai":
            _llm_adapter_instance = OpenAILLMAdapter()
        else:
            _llm_adapter_instance = MockLLMAdapter()
    return _llm_adapter_instance


def set_llm_adapter(adapter: LLMProviderProtocol | None) -> None:
    global _llm_adapter_instance
    _llm_adapter_instance = adapter


__all__ = [
    "ChatMessage",
    "ToolCall",
    "ToolDefinition",
    "LLMResponse",
    "LLMProviderProtocol",
    "MockLLMAdapter",
    "OpenAILLMAdapter",
    "get_llm_adapter",
    "set_llm_adapter",
]

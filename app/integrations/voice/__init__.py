from app.core.config import settings
from app.integrations.voice.mock_voice import MockSTTAdapter, MockTTSAdapter
from app.integrations.voice.protocol import (
    AudioPayload,
    SpeechToTextProtocol,
    STTResult,
    TextToSpeechProtocol,
    TTSResult,
)
from app.integrations.voice.whisper_voice import (
    OpenAITTSAdapter,
    OpenAIWhisperSTTAdapter,
)

_stt_adapter_instance: SpeechToTextProtocol | None = None
_tts_adapter_instance: TextToSpeechProtocol | None = None


def get_stt_adapter() -> SpeechToTextProtocol:
    global _stt_adapter_instance
    if _stt_adapter_instance is None:
        if settings.VOICE_STT_PROVIDER == "openai":
            _stt_adapter_instance = OpenAIWhisperSTTAdapter()
        else:
            _stt_adapter_instance = MockSTTAdapter()
    return _stt_adapter_instance


def get_tts_adapter() -> TextToSpeechProtocol:
    global _tts_adapter_instance
    if _tts_adapter_instance is None:
        if settings.VOICE_TTS_PROVIDER == "openai":
            _tts_adapter_instance = OpenAITTSAdapter()
        else:
            _tts_adapter_instance = MockTTSAdapter()
    return _tts_adapter_instance


def set_stt_adapter(adapter: SpeechToTextProtocol | None) -> None:
    global _stt_adapter_instance
    _stt_adapter_instance = adapter


def set_tts_adapter(adapter: TextToSpeechProtocol | None) -> None:
    global _tts_adapter_instance
    _tts_adapter_instance = adapter


__all__ = [
    "AudioPayload",
    "STTResult",
    "TTSResult",
    "SpeechToTextProtocol",
    "TextToSpeechProtocol",
    "MockSTTAdapter",
    "MockTTSAdapter",
    "OpenAIWhisperSTTAdapter",
    "OpenAITTSAdapter",
    "get_stt_adapter",
    "get_tts_adapter",
    "set_stt_adapter",
    "set_tts_adapter",
]

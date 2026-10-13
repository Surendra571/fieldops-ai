from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AudioPayload:
    content: bytes
    format: str = "wav"  # wav, mp3, ogg, webm
    sample_rate: int = 16000
    channels: int = 1


@dataclass(frozen=True)
class STTResult:
    text: str
    confidence: float = 1.0
    language: str = "en"
    duration_seconds: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class TTSResult:
    audio_content: bytes
    format: str = "wav"
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    metadata: dict[str, Any] | None = None


class SpeechToTextProtocol(Protocol):
    """
    Provider-independent interface for audio speech recognition (transcription).
    """

    async def transcribe(self, audio: AudioPayload, prompt: str | None = None) -> STTResult:
        """Convert spoken audio stream/file to clean text."""
        ...


class TextToSpeechProtocol(Protocol):
    """
    Provider-independent interface for speech synthesis.
    """

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        """Convert assistant response text to spoken audio."""
        ...

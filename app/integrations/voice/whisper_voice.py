import io
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.voice.protocol import (
    AudioPayload,
    SpeechToTextProtocol,
    STTResult,
    TextToSpeechProtocol,
    TTSResult,
)

logger = logging.getLogger(__name__)


class OpenAIWhisperSTTAdapter(SpeechToTextProtocol):
    """
    OpenAI Whisper audio transcription adapter.
    Uses OpenAI's /v1/audio/transcriptions endpoint.
    """

    def __init__(self, api_key: str | None = None, model: str = "whisper-1") -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe(self, audio: AudioPayload, prompt: str | None = None) -> STTResult:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured for Whisper STT.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # Format audio into multipart/form-data
        filename = f"audio.{audio.format}"
        files = {
            "file": (filename, io.BytesIO(audio.content), f"audio/{audio.format}"),
        }
        data: dict[str, Any] = {
            "model": self.model,
            "response_format": "json",
        }
        if prompt:
            data["prompt"] = prompt

        async with httpx.AsyncClient(timeout=settings.AGENT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
            res_json = response.json()
            return STTResult(
                text=res_json.get("text", "").strip(),
                confidence=1.0,
                language="en",
                metadata={"provider": "openai_whisper", "model": self.model},
            )


class OpenAITTSAdapter(TextToSpeechProtocol):
    """
    OpenAI Speech synthesis adapter.
    Uses OpenAI's /v1/audio/speech endpoint.
    """

    def __init__(
        self, api_key: str | None = None, model: str = "tts-1", voice: str = "alloy"
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.default_voice = voice
        self.api_url = "https://api.openai.com/v1/audio/speech"

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured for OpenAI TTS.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice or self.default_voice,
            "response_format": "wav",
        }

        async with httpx.AsyncClient(timeout=settings.AGENT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            wav_bytes = response.content

            return TTSResult(
                audio_content=wav_bytes,
                format="wav",
                sample_rate=24000,
                duration_seconds=max(0.5, len(text) * 0.05),
                metadata={
                    "provider": "openai_tts",
                    "model": self.model,
                    "voice": voice or self.default_voice,
                },
            )

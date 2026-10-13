import struct

from app.integrations.voice.protocol import (
    AudioPayload,
    SpeechToTextProtocol,
    STTResult,
    TextToSpeechProtocol,
    TTSResult,
)


def _generate_synthetic_wav(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """
    Generate a minimal valid 16-bit mono PCM WAV file in memory.
    """
    num_samples = int(sample_rate * duration_seconds)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample
    file_size = 36 + data_size

    # RIFF header
    header = bytearray(b"RIFF")
    header.extend(struct.pack("<I", file_size))
    header.extend(b"WAVE")
    # fmt chunk
    header.extend(b"fmt ")
    header.extend(struct.pack("<I", 16))  # Subchunk1Size (16 for PCM)
    header.extend(struct.pack("<H", 1))  # AudioFormat (1 = PCM)
    header.extend(struct.pack("<H", 1))  # NumChannels (1 = Mono)
    header.extend(struct.pack("<I", sample_rate))  # SampleRate
    header.extend(
        struct.pack("<I", sample_rate * 2)
    )  # ByteRate (SampleRate * NumChannels * BitsPerSample/8)
    header.extend(struct.pack("<H", 2))  # BlockAlign (NumChannels * BitsPerSample/8)
    header.extend(struct.pack("<H", 16))  # BitsPerSample (16)
    # data chunk
    header.extend(b"data")
    header.extend(struct.pack("<I", data_size))

    # Silence/zero samples
    pcm_data = b"\x00" * data_size
    return bytes(header) + pcm_data


class MockSTTAdapter(SpeechToTextProtocol):
    """
    Deterministic Mock Speech-to-Text adapter for tests and offline development.
    If the audio bytes represent utf-8 text (e.g. in test fixtures), it decodes it directly.
    Otherwise, returns a deterministic or registered transcription.
    """

    def __init__(
        self,
        default_transcript: str = "My AC is leaking water at 742 Evergreen Terrace and I need a technician.",
    ) -> None:
        self.default_transcript = default_transcript
        self._custom_transcripts: dict[bytes, str] = {}
        self.transcription_history: list[AudioPayload] = []

    def register_transcript(self, audio_bytes: bytes, transcript: str) -> None:
        self._custom_transcripts[audio_bytes] = transcript

    async def transcribe(self, audio: AudioPayload, prompt: str | None = None) -> STTResult:
        self.transcription_history.append(audio)

        # Check explicit registration
        if audio.content in self._custom_transcripts:
            return STTResult(
                text=self._custom_transcripts[audio.content],
                confidence=0.99,
                language="en",
                duration_seconds=2.5,
                metadata={"provider": "mock", "registered": True},
            )

        # Check if audio content is encoded UTF-8 text (common in mock test payloads)
        try:
            # If it's a WAV header, don't try decoding raw binary as string unless preceded by a text marker
            if not audio.content.startswith(b"RIFF"):
                text_attempt = audio.content.decode("utf-8").strip()
                if len(text_attempt) > 0 and all(
                    c.isprintable() or c in "\r\n\t" for c in text_attempt
                ):
                    return STTResult(
                        text=text_attempt,
                        confidence=1.0,
                        language="en",
                        duration_seconds=max(1.0, len(text_attempt) * 0.05),
                        metadata={"provider": "mock", "decoded_raw": True},
                    )
        except Exception:
            pass

        return STTResult(
            text=self.default_transcript,
            confidence=0.95,
            language="en",
            duration_seconds=3.0,
            metadata={"provider": "mock", "default": True},
        )


class MockTTSAdapter(TextToSpeechProtocol):
    """
    Deterministic Mock Text-to-Speech adapter producing valid WAV bytes.
    """

    def __init__(self) -> None:
        self.synthesis_history: list[str] = []

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        self.synthesis_history.append(text)
        duration = max(0.5, len(text) * 0.04)
        wav_bytes = _generate_synthetic_wav(duration_seconds=duration, sample_rate=16000)

        return TTSResult(
            audio_content=wav_bytes,
            format="wav",
            duration_seconds=duration,
            sample_rate=16000,
            metadata={"provider": "mock", "text_length": len(text), "voice": voice or "alloy"},
        )

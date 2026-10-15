"""Text-to-Speech (TTS) service layer supporting Piper, Kokoro, and browser fallback."""

from abc import ABC, abstractmethod
import asyncio
from typing import AsyncGenerator, Optional
import wave
import io
import math

from app.core.config import settings
from app.core.logging import logger


class BaseTTSProvider(ABC):
    """Abstract Base Class for Text-to-Speech synthesis."""

    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Yield synthesized audio byte chunks (e.g. PCM/WAV) in streaming fashion."""
        pass


class BrowserTTSProvider(BaseTTSProvider):
    """Browser SpeechSynthesis fallback mode.

    The browser directly uses Web Speech API for zero-latency, CPU-free local speech generation.
    Server signals audio events to coordinate UI states.
    """

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        # Generate a small silent or dummy audio frame to satisfy protocol
        yield b""


class MockTTSProvider(BaseTTSProvider):
    """Deterministic TTS provider generating a lightweight sine beep WAV for test pipelines."""

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        sample_rate = 16000
        duration_s = 0.5
        frequency = 440.0
        num_samples = int(sample_rate * duration_s)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            samples = bytearray()
            for i in range(num_samples):
                val = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
                samples.extend(val.to_bytes(2, byteorder="little", signed=True))
            wf.writeframes(samples)

        yield buffer.getvalue()


class PiperTTSProvider(BaseTTSProvider):
    """Local neural TTS via Piper binary."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.PIPER_MODEL_PATH

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        try:
            # Launch piper process
            process = await asyncio.create_subprocess_exec(
                "piper",
                "--model",
                self.model_path,
                "--output-raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await process.communicate(input=text.encode("utf-8"))
            if stdout:
                # Yield in 4KB chunks
                chunk_size = 4096
                for i in range(0, len(stdout), chunk_size):
                    yield stdout[i : i + chunk_size]
        except Exception as e:
            logger.warning(f"Piper TTS execution failed: {e}. Falling back to Browser TTS.")
            async for chunk in BrowserTTSProvider().synthesize_stream(text):
                yield chunk


_tts_instance: Optional[BaseTTSProvider] = None


def get_tts_provider() -> BaseTTSProvider:
    """Singleton factory for TTS engine."""
    global _tts_instance
    if _tts_instance is None:
        if settings.TTS_PROVIDER == "piper":
            _tts_instance = PiperTTSProvider()
        elif settings.TTS_PROVIDER == "mock":
            _tts_instance = MockTTSProvider()
        else:
            _tts_instance = BrowserTTSProvider()
    return _tts_instance

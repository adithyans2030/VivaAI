"""Text-to-Speech (TTS) service layer supporting EdgeTTS, Piper, Kokoro, and browser fallback."""

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

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        """Synthesize text into complete audio bytes (WAV/MP3). Returns None if browser TTS is active."""
        chunks = []
        async for chunk in self.synthesize_stream(text):
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks) if chunks else None

    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Yield synthesized audio byte chunks in streaming fashion."""
        pass


class BrowserTTSProvider(BaseTTSProvider):
    """Browser SpeechSynthesis fallback mode.

    The browser directly uses Web Speech API for zero-latency, CPU-free local speech generation.
    Server returns None for audio bytes, signaling the client to use browser speech synthesis.
    """

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        return None

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        yield b""


class MockTTSProvider(BaseTTSProvider):
    """Deterministic TTS provider generating a lightweight sine beep WAV for test pipelines."""

    def _generate_sine_wav(self) -> bytes:
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
        return buffer.getvalue()

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        return self._generate_sine_wav()

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        yield self._generate_sine_wav()


class EdgeTTSProvider(BaseTTSProvider):
    """High-quality neural server-side TTS using edge-tts (fast, neural quality)."""

    def __init__(self, voice: str = "en-US-JennyNeural"):
        self.voice = voice

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
            data = buffer.getvalue()
            return data if data else None
        except Exception as e:
            logger.warning(f"EdgeTTS synthesis failed: {e}. Falling back to browser speech.")
            return None

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            logger.warning(f"EdgeTTS stream failed: {e}")
            yield b""


class PiperTTSProvider(BaseTTSProvider):
    """Local neural TTS via Piper binary."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.PIPER_MODEL_PATH

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        try:
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
        elif settings.TTS_PROVIDER == "edge":
            _tts_instance = EdgeTTSProvider()
        elif settings.TTS_PROVIDER == "mock":
            _tts_instance = MockTTSProvider()
        else:
            _tts_instance = BrowserTTSProvider()
    return _tts_instance

"""Text-to-Speech (TTS) service layer supporting EdgeTTS, Piper, Kokoro, and browser fallback."""

import asyncio
import io
import json
import math
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncGenerator, Optional

from app.core.config import settings
from app.core.logging import logger


class BaseTTSProvider(ABC):
    """Abstract Base Class for Text-to-Speech synthesis."""

    # MIME type of the bytes this provider produces; sent to the client so it can play them.
    mime_type: Optional[str] = None

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        """Synthesize text into complete audio bytes (WAV/MP3). Returns None if browser TTS is active."""
        chunks = []
        async for chunk in self.synthesize_stream(text):
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks) if chunks else None

    @abstractmethod
    def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Yield synthesized audio byte chunks in streaming fashion."""
        pass


class BrowserTTSProvider(BaseTTSProvider):
    """Browser SpeechSynthesis fallback mode.

    The browser directly uses Web Speech API for zero-latency, CPU-free local speech generation.
    Server returns None for audio bytes, signaling the client to use browser speech synthesis.
    """

    mime_type = None

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        return None

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        yield b""


class MockTTSProvider(BaseTTSProvider):
    """Deterministic TTS provider generating a lightweight sine beep WAV for test pipelines."""

    mime_type = "audio/wav"

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

    mime_type = "audio/mpeg"

    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or settings.EDGE_TTS_VOICE

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
    """Local neural TTS via Piper binary.

    Piper's --output-raw emits headerless 16-bit mono PCM, which browsers cannot play,
    so the output is wrapped in a WAV container at the voice's sample rate.
    """

    mime_type = "audio/wav"
    DEFAULT_SAMPLE_RATE = 22050

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.PIPER_MODEL_PATH
        self.sample_rate = self._read_sample_rate(self.model_path)

    @classmethod
    def _read_sample_rate(cls, model_path: str) -> int:
        """Piper voices ship a `<model>.onnx.json` config holding `audio.sample_rate`."""
        try:
            config = json.loads(Path(f"{model_path}.json").read_text(encoding="utf-8"))
            return int(config["audio"]["sample_rate"])
        except Exception:
            return cls.DEFAULT_SAMPLE_RATE

    async def _run_piper(self, text: str) -> bytes:
        process = await asyncio.create_subprocess_exec(
            "piper",
            "--model",
            self.model_path,
            "--output-raw",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(input=text.encode("utf-8"))
        if process.returncode != 0:
            raise RuntimeError(f"piper exited {process.returncode}: {stderr.decode(errors='replace')[:200]}")
        return stdout

    def _wrap_wav(self, pcm: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm)
        return buffer.getvalue()

    async def synthesize_audio(self, text: str) -> Optional[bytes]:
        try:
            pcm = await self._run_piper(text)
        except Exception as e:
            logger.warning(f"Piper TTS execution failed: {e}. Falling back to browser speech.")
            return None
        return self._wrap_wav(pcm) if pcm else None

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        audio = await self.synthesize_audio(text)
        if audio:
            yield audio


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
            if settings.TTS_PROVIDER != "browser":
                logger.warning(f"TTS_PROVIDER='{settings.TTS_PROVIDER}' is not available; using browser speech.")
            _tts_instance = BrowserTTSProvider()
    return _tts_instance

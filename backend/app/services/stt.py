"""Speech-to-Text (STT) service layer with faster-whisper and word-level timestamps."""

import asyncio
import io
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional, Union

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger


class STTWord(BaseModel):
    word: str
    start: float
    end: float
    probability: float


class STTResult(BaseModel):
    text: str
    language: str = "en"
    duration_seconds: float = 0.0
    words: List[STTWord] = []


class BaseSTTProvider(ABC):
    """Abstract Base Class for Speech-to-Text engines."""

    @abstractmethod
    async def transcribe(self, audio_data: Union[bytes, Path, str], initial_prompt: Optional[str] = None) -> STTResult:
        """Transcribe audio bytes or audio file into text with word timestamps."""
        pass

    @abstractmethod
    def is_model_loaded(self) -> bool:
        """Check if model weights are loaded and ready."""
        pass


class MockSTTProvider(BaseSTTProvider):
    """Deterministic Mock STT provider for CI, testing, and rapid dev."""

    def is_model_loaded(self) -> bool:
        return True

    async def transcribe(self, audio_data: Union[bytes, Path, str], initial_prompt: Optional[str] = None) -> STTResult:
        # Calculate approximate duration based on bytes if available
        duration = 3.5
        if isinstance(audio_data, bytes):
            duration = max(1.0, round(len(audio_data) / 32000.0, 2))

        sample_words = [
            STTWord(word="The", start=0.1, end=0.3, probability=0.99),
            STTWord(word="four", start=0.35, end=0.6, probability=0.98),
            STTWord(word="necessary", start=0.65, end=1.1, probability=0.95),
            STTWord(word="conditions", start=1.15, end=1.65, probability=0.97),
            STTWord(word="for", start=1.7, end=1.85, probability=0.99),
            STTWord(word="deadlock", start=1.9, end=2.4, probability=0.98),
            STTWord(word="are", start=2.45, end=2.6, probability=0.99),
            STTWord(word="mutual", start=2.65, end=3.0, probability=0.96),
            STTWord(word="exclusion,", start=3.05, end=3.6, probability=0.97),
            STTWord(word="hold", start=3.65, end=3.9, probability=0.98),
            STTWord(word="and", start=3.95, end=4.1, probability=0.99),
            STTWord(word="wait,", start=4.15, end=4.5, probability=0.97),
            STTWord(word="no", start=4.55, end=4.7, probability=0.98),
            STTWord(word="preemption,", start=4.75, end=5.3, probability=0.96),
            STTWord(word="and", start=5.35, end=5.5, probability=0.99),
            STTWord(word="circular", start=5.55, end=6.0, probability=0.97),
            STTWord(word="wait.", start=6.05, end=6.4, probability=0.98),
        ]

        text = "The four necessary conditions for deadlock are mutual exclusion, hold and wait, no preemption, and circular wait."
        return STTResult(
            text=text,
            language="en",
            duration_seconds=max(duration, 6.4),
            words=sample_words,
        )


def _read_pcm16_wav(audio: Union[bytes, Path, str]) -> Optional[Any]:
    """Return float32 samples for a 16 kHz mono 16-bit WAV, or None for anything else."""
    import wave

    import numpy as np

    try:
        source = io.BytesIO(audio) if isinstance(audio, bytes) else str(audio)
        with wave.open(source, "rb") as wf:
            if (wf.getframerate(), wf.getnchannels(), wf.getsampwidth()) != (16000, 1, 2):
                return None
            frames = wf.readframes(wf.getnframes())
    except (wave.Error, EOFError, OSError):
        return None
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def _smoke_test(model: Any) -> None:
    """Run one tiny inference so device/runtime problems surface at startup."""
    import numpy as np

    segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1)
    list(segments)


class WhisperSTTProvider(BaseSTTProvider):
    """Production faster-whisper STT with CUDA/GPU acceleration and word timestamps."""

    def __init__(self) -> None:
        self._model = None
        self._active_device = settings.WHISPER_DEVICE
        self._init_model()

    def is_model_loaded(self) -> bool:
        return self._model is not None

    def get_active_device(self) -> str:
        return self._active_device

    def _init_model(self) -> None:
        try:
            from faster_whisper import WhisperModel

            model_size = settings.WHISPER_MODEL
            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE

            logger.info(
                f"Loading faster-whisper model '{model_size}' on device={device} (compute_type={compute_type})..."
            )
            model = WhisperModel(
                model_size_or_path=model_size,
                device=device,
                compute_type=compute_type,
            )
            # Loading can succeed while inference fails (e.g. CUDA runtime DLLs missing), so prove it works now
            # instead of failing on every student answer later.
            _smoke_test(model)
            self._model = model
            self._active_device = device
            logger.info(f"faster-whisper model loaded and verified on {device}.")
        except Exception as e:
            logger.warning(
                f"CRITICAL WARNING: Failed to initialize faster-whisper on requested device '{settings.WHISPER_DEVICE}': {e}. "
                "Attempting fallback to CPU..."
            )
            try:
                from faster_whisper import WhisperModel

                model = WhisperModel(
                    model_size_or_path=settings.WHISPER_MODEL,
                    device="cpu",
                    compute_type="int8",
                )
                _smoke_test(model)
                self._model = model
                self._active_device = "cpu"
                logger.warning("Fallback CPU faster-whisper model initialized. Transcription latency may increase.")
            except Exception as cpu_err:
                logger.error(f"CPU fallback for faster-whisper also failed: {cpu_err}.")
                self._model = None
                # If demo mode or testing, allow mock fallback with clear log; otherwise fail explicitly
                if settings.DEMO_MODE or settings.ENVIRONMENT == "testing":
                    logger.warning("DEMO_MODE/TESTING is active: Using MockSTTProvider.")
                else:
                    raise RuntimeError(
                        f"Failed to initialize faster-whisper STT on both '{settings.WHISPER_DEVICE}' and 'cpu': {cpu_err}. "
                        "Install faster-whisper and torch, or run with DEMO_MODE=true / ENVIRONMENT=testing."
                    )

    async def transcribe(self, audio_data: Union[bytes, Path, str], initial_prompt: Optional[str] = None) -> STTResult:
        if self._model is None:
            if settings.DEMO_MODE or settings.ENVIRONMENT == "testing":
                return await MockSTTProvider().transcribe(audio_data, initial_prompt=initial_prompt)
            raise RuntimeError("Whisper model is not loaded. Cannot transcribe audio without a valid STT model.")

        # Prefer handing Whisper raw samples: our pipeline already produces 16 kHz mono WAV, and this
        # avoids faster-whisper's PyAV decoder, whose API changes between releases (av 19 broke it).
        pcm = _read_pcm16_wav(audio_data)
        audio_source: Any
        if pcm is not None:
            audio_source = pcm
        elif isinstance(audio_data, bytes):
            audio_source = io.BytesIO(audio_data)
        elif isinstance(audio_data, Path):
            audio_source = str(audio_data)
        else:
            audio_source = audio_data

        beam_size = getattr(settings, "WHISPER_BEAM_SIZE", 1)
        language = getattr(settings, "WHISPER_LANGUAGE", "en")
        if language == "auto":
            language = None

        def _sync_transcribe():
            segments_gen, info = self._model.transcribe(
                audio_source,
                beam_size=beam_size,
                word_timestamps=True,
                language=language,
                initial_prompt=initial_prompt,
            )
            # Evaluate the generator inside the worker thread to perform real inference
            return list(segments_gen), info

        segments, info = await asyncio.to_thread(_sync_transcribe)

        words_list: List[STTWord] = []
        transcript_parts: List[str] = []

        for segment in segments:
            transcript_parts.append(segment.text.strip())
            if segment.words:
                for w in segment.words:
                    words_list.append(
                        STTWord(
                            word=w.word.strip(),
                            start=round(w.start, 2),
                            end=round(w.end, 2),
                            probability=round(w.probability, 2),
                        )
                    )

        full_text = " ".join(transcript_parts).strip()
        return STTResult(
            text=full_text,
            language=info.language or "en",
            duration_seconds=round(info.duration, 2),
            words=words_list,
        )


_stt_instance: Optional[BaseSTTProvider] = None
# The model is preloaded from a worker thread at startup; a student answer arriving meanwhile must
# wait for that load rather than start a second one.
_stt_lock = threading.Lock()


def get_stt_provider() -> BaseSTTProvider:
    """Singleton factory for STT engine."""
    global _stt_instance
    if _stt_instance is not None:
        return _stt_instance
    with _stt_lock:
        return _create_stt_provider()


def _create_stt_provider() -> BaseSTTProvider:
    global _stt_instance
    if _stt_instance is None:
        if settings.STT_PROVIDER == "whisper":
            _stt_instance = WhisperSTTProvider()
        else:
            if not settings.DEMO_MODE and settings.ENVIRONMENT != "testing":
                raise RuntimeError(
                    "STT_PROVIDER='mock' is only permitted when ENVIRONMENT='testing' or DEMO_MODE=True. "
                    "Set STT_PROVIDER='whisper' or configure DEMO_MODE=True."
                )
            _stt_instance = MockSTTProvider()
    return _stt_instance

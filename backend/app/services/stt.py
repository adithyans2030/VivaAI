"""Speech-to-Text (STT) service layer with faster-whisper and word-level timestamps."""

from abc import ABC, abstractmethod
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import wave

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
    async def transcribe(self, audio_data: Union[bytes, Path, str]) -> STTResult:
        """Transcribe audio bytes or audio file into text with word timestamps."""
        pass


class MockSTTProvider(BaseSTTProvider):
    """Deterministic Mock STT provider for CI, testing, and rapid dev."""

    async def transcribe(self, audio_data: Union[bytes, Path, str]) -> STTResult:
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


class WhisperSTTProvider(BaseSTTProvider):
    """Production faster-whisper STT with CUDA/GPU acceleration and word timestamps."""

    def __init__(self) -> None:
        self._model = None
        self._init_model()

    def _init_model(self) -> None:
        try:
            from faster_whisper import WhisperModel

            model_size = settings.WHISPER_MODEL
            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE

            logger.info(
                f"Loading faster-whisper model '{model_size}' on device={device} (compute_type={compute_type})..."
            )
            self._model = WhisperModel(
                model_size_or_path=model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info("faster-whisper model loaded successfully.")
        except Exception as e:
            logger.warning(
                f"Failed to initialize faster-whisper on {settings.WHISPER_DEVICE}: {e}. Falling back to CPU / mock mode."
            )
            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    model_size_or_path="base.en",
                    device="cpu",
                    compute_type="int8",
                )
                logger.info("Fallback CPU faster-whisper model initialized.")
            except Exception as cpu_err:
                logger.error(f"CPU fallback also failed: {cpu_err}. Switching to MockSTTProvider.")
                self._model = None

    async def transcribe(self, audio_data: Union[bytes, Path, str]) -> STTResult:
        if self._model is None:
            # Fallback to mock if whisper couldn't load
            return await MockSTTProvider().transcribe(audio_data)

        # Handle in-memory bytes or file path
        if isinstance(audio_data, bytes):
            audio_source = io.BytesIO(audio_data)
        elif isinstance(audio_data, Path):
            audio_source = str(audio_data)
        else:
            audio_source = audio_data

        segments, info = self._model.transcribe(
            audio_source,
            beam_size=5,
            word_timestamps=True,
            language="en",
        )

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


def get_stt_provider() -> BaseSTTProvider:
    """Singleton factory for STT engine."""
    global _stt_instance
    if _stt_instance is None:
        if settings.STT_PROVIDER == "whisper":
            _stt_instance = WhisperSTTProvider()
        else:
            _stt_instance = MockSTTProvider()
    return _stt_instance

"""STT and TTS provider tests with faster-whisper, edge-tts and piper stubbed out."""

import asyncio
import io
import json
import sys
import types
import wave
from pathlib import Path
from typing import Any, AsyncGenerator, List, Optional

import pytest

from app.core.config import settings
from app.services import stt as stt_module
from app.services import tts as tts_module
from app.services.stt import MockSTTProvider, WhisperSTTProvider, get_stt_provider
from app.services.tts import (
    BrowserTTSProvider,
    EdgeTTSProvider,
    MockTTSProvider,
    PiperTTSProvider,
    get_tts_provider,
)

# --------------------------------------------------------------------------- faster-whisper stub


class FakeWord:
    def __init__(self, word: str, start: float, end: float, probability: float) -> None:
        self.word, self.start, self.end, self.probability = word, start, end, probability


class FakeSegment:
    def __init__(self, text: str, words: List[FakeWord]) -> None:
        self.text, self.words = text, words


class FakeWhisperModel:
    instances: List["FakeWhisperModel"] = []
    fail_on_devices: set = set()

    def __init__(self, model_size_or_path: str, device: str, compute_type: str) -> None:
        if device in self.fail_on_devices:
            raise RuntimeError(f"CUDA unavailable on {device}")
        self.model, self.device = model_size_or_path, device
        self.calls: List[dict] = []
        FakeWhisperModel.instances.append(self)

    def transcribe(self, source: Any, **kwargs: Any) -> tuple:
        self.calls.append({"source": source, **kwargs})
        segments = iter(
            [
                FakeSegment(
                    " Mutual exclusion ",
                    [FakeWord(" Mutual", 0.0, 0.412, 0.987), FakeWord(" exclusion", 0.5, 1.0, 0.9)],
                ),
                FakeSegment(" is required. ", []),
            ]
        )
        return segments, types.SimpleNamespace(language="en", duration=2.345)


@pytest.fixture
def fake_whisper(monkeypatch: pytest.MonkeyPatch) -> type:
    FakeWhisperModel.instances = []
    FakeWhisperModel.fail_on_devices = set()
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(settings, "WHISPER_DEVICE", "cuda")
    return FakeWhisperModel


async def test_whisper_transcribes_with_word_timestamps(fake_whisper: type, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WHISPER_LANGUAGE", "auto", raising=False)
    provider = WhisperSTTProvider()
    assert provider.is_model_loaded() and provider.get_active_device() == "cuda"

    result = await provider.transcribe(b"RIFFfake", initial_prompt="Operating systems viva")

    assert result.text == "Mutual exclusion is required."
    assert result.duration_seconds == pytest.approx(2.345, abs=0.01)
    assert [(w.word, w.start, w.end) for w in result.words] == [("Mutual", 0.0, 0.41), ("exclusion", 0.5, 1.0)]
    call = fake_whisper.instances[0].calls[0]
    assert isinstance(call["source"], io.BytesIO)
    assert call["word_timestamps"] is True
    assert call["language"] is None  # "auto" lets whisper detect
    assert call["initial_prompt"] == "Operating systems viva"


async def test_whisper_accepts_file_paths(fake_whisper: type, tmp_path: Path) -> None:
    provider = WhisperSTTProvider()
    await provider.transcribe(tmp_path / "a.wav")
    assert fake_whisper.instances[0].calls[0]["source"] == str(tmp_path / "a.wav")


def test_whisper_falls_back_to_cpu(fake_whisper: type) -> None:
    fake_whisper.fail_on_devices = {"cuda"}
    provider = WhisperSTTProvider()
    assert provider.get_active_device() == "cpu"
    assert fake_whisper.instances[0].model == "base.en"


async def test_whisper_unavailable_raises_outside_demo(fake_whisper: type, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_whisper.fail_on_devices = {"cuda", "cpu"}
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="Failed to initialize faster-whisper"):
        WhisperSTTProvider()


async def test_whisper_unavailable_uses_mock_only_in_testing(fake_whisper: type) -> None:
    fake_whisper.fail_on_devices = {"cuda", "cpu"}
    provider = WhisperSTTProvider()
    assert not provider.is_model_loaded()
    assert (await provider.transcribe(b"x" * 64000)).words


async def test_mock_stt_duration_tracks_audio_length() -> None:
    assert (await MockSTTProvider().transcribe(b"\x00" * 32000 * 10)).duration_seconds == 10.0


def test_stt_factory(fake_whisper: type, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stt_module, "_stt_instance", None)
    monkeypatch.setattr(settings, "STT_PROVIDER", "whisper")
    assert isinstance(get_stt_provider(), WhisperSTTProvider)

    monkeypatch.setattr(stt_module, "_stt_instance", None)
    monkeypatch.setattr(settings, "STT_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with pytest.raises(RuntimeError, match="only permitted"):
        get_stt_provider()


# --------------------------------------------------------------------------- TTS


async def test_browser_tts_defers_to_client() -> None:
    provider = BrowserTTSProvider()
    assert await provider.synthesize_audio("hi") is None
    assert provider.mime_type is None


async def test_mock_tts_produces_valid_wav() -> None:
    audio = await MockTTSProvider().synthesize_audio("hi")
    assert audio is not None
    with wave.open(io.BytesIO(audio)) as wf:
        assert wf.getframerate() == 16000 and wf.getnframes() == 8000


@pytest.fixture
def fake_edge(monkeypatch: pytest.MonkeyPatch) -> List[tuple]:
    created: List[tuple] = []

    class Communicate:
        def __init__(self, text: str, voice: str) -> None:
            created.append((text, voice))
            if text == "boom":
                raise RuntimeError("network down")

        async def stream(self) -> AsyncGenerator[dict, None]:
            yield {"type": "WordBoundary"}
            yield {"type": "audio", "data": b"ID3"}
            yield {"type": "audio", "data": b"mp3"}

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    return created


async def test_edge_tts_collects_audio_chunks(fake_edge: List[tuple], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "EDGE_TTS_VOICE", "en-IN-NeerjaNeural")
    provider = EdgeTTSProvider()
    assert await provider.synthesize_audio("What is paging?") == b"ID3mp3"
    assert [c async for c in provider.synthesize_stream("x")] == [b"ID3", b"mp3"]
    assert fake_edge[0] == ("What is paging?", "en-IN-NeerjaNeural")
    assert provider.mime_type == "audio/mpeg"


async def test_edge_tts_failure_falls_back_to_browser(fake_edge: List[tuple]) -> None:
    assert await EdgeTTSProvider().synthesize_audio("boom") is None


class FakeProcess:
    def __init__(self, stdout: bytes, returncode: int = 0) -> None:
        self._stdout, self.returncode = stdout, returncode
        self.stdin_text: Optional[bytes] = None

    async def communicate(self, input: bytes) -> tuple:
        self.stdin_text = input
        return self._stdout, b"bad voice" if self.returncode else b""


async def test_piper_wraps_raw_pcm_as_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = tmp_path / "en_IN-voice.onnx"
    Path(f"{model}.json").write_text(json.dumps({"audio": {"sample_rate": 16000}}))
    proc = FakeProcess(stdout=b"\x01\x00" * 1600)
    captured: List[tuple] = []

    async def fake_exec(*args: str, **kwargs: Any) -> FakeProcess:
        captured.append(args)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    provider = PiperTTSProvider(model_path=str(model))
    audio = await provider.synthesize_audio("Explain paging.")

    assert audio is not None
    with wave.open(io.BytesIO(audio)) as wf:
        assert (wf.getframerate(), wf.getsampwidth(), wf.getnframes()) == (16000, 2, 1600)
    assert captured[0] == ("piper", "--model", str(model), "--output-raw")
    assert proc.stdin_text == b"Explain paging."
    assert [c async for c in provider.synthesize_stream("x")] == [audio]


async def test_piper_failure_falls_back_to_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_exec(*args: str, **kwargs: Any) -> FakeProcess:
        return FakeProcess(stdout=b"", returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    provider = PiperTTSProvider(model_path="/missing/voice.onnx")
    assert provider.sample_rate == PiperTTSProvider.DEFAULT_SAMPLE_RATE
    assert await provider.synthesize_audio("hi") is None


@pytest.mark.parametrize(
    ("name", "cls"),
    [("piper", PiperTTSProvider), ("edge", EdgeTTSProvider), ("mock", MockTTSProvider), ("kokoro", BrowserTTSProvider)],
)
def test_tts_factory(name: str, cls: type, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts_module, "_tts_instance", None)
    monkeypatch.setattr(settings, "TTS_PROVIDER", name)
    assert isinstance(get_tts_provider(), cls)

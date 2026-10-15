"""Tests for STT service and word-level timestamps."""

import pytest
from app.services.stt import MockSTTProvider, STTResult, get_stt_provider


@pytest.mark.asyncio
async def test_mock_stt_transcription():
    provider = MockSTTProvider()
    dummy_audio = b"\x00\x00" * 16000  # 1 second of 16kHz 16-bit PCM

    result = await provider.transcribe(dummy_audio)
    assert isinstance(result, STTResult)
    assert len(result.text) > 0
    assert result.duration_seconds > 0
    assert len(result.words) > 0

    # Verify word timestamps structure
    first_word = result.words[0]
    assert first_word.word == "The"
    assert first_word.start >= 0
    assert first_word.end > first_word.start
    assert 0.0 <= first_word.probability <= 1.0


@pytest.mark.asyncio
async def test_get_stt_provider_singleton():
    provider_1 = get_stt_provider()
    provider_2 = get_stt_provider()
    assert provider_1 is provider_2

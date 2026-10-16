"""Audio container format detection and transcoding service."""

import asyncio
from pathlib import Path
import shutil
import subprocess
from typing import Tuple

from app.core.logging import logger


def detect_audio_format(audio_bytes: bytes) -> str:
    """Identify container format from magic bytes."""
    if len(audio_bytes) < 12:
        return "unknown"
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return "wav"
    if audio_bytes[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if audio_bytes[:4] == b"OggS":
        return "ogg"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return "mp3"
    return "raw"


def _sync_transcode_to_wav(audio_bytes: bytes, target_path: Path) -> Path:
    """Synchronous file write and ffmpeg transcode to 16kHz mono WAV."""
    fmt = detect_audio_format(audio_bytes)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "wav":
        target_path.write_bytes(audio_bytes)
        return target_path

    # If ffmpeg is available, transcode WebM/Ogg/MP3 to 16kHz 16-bit mono WAV
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        temp_input = target_path.with_suffix(f".input_{fmt}")
        try:
            temp_input.write_bytes(audio_bytes)
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(temp_input),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(target_path),
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 0:
                return target_path
            logger.warning(
                f"ffmpeg transcode failed (exit {res.returncode}): {res.stderr.decode('utf-8', errors='ignore')[:300]}. "
                "Writing raw bytes."
            )
        except Exception as e:
            logger.warning(f"Error during ffmpeg transcoding: {e}. Writing raw bytes.")
        finally:
            if temp_input.exists():
                try:
                    temp_input.unlink()
                except OSError:
                    pass

    # Fallback: write bytes directly to target path
    target_path.write_bytes(audio_bytes)
    return target_path


async def transcode_to_wav(audio_bytes: bytes, target_path: Path) -> Path:
    """Asynchronously transcode candidate audio bytes to 16kHz mono WAV."""
    return await asyncio.to_thread(_sync_transcode_to_wav, audio_bytes, target_path)

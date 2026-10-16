"""WebSocket connection manager for handling active viva sessions and backpressure."""

import asyncio
from typing import Dict, Optional, Set
from fastapi import WebSocket

from app.core.logging import logger


# 5 minutes of 16 kHz 16-bit mono audio is 5 * 60 * 16000 * 2 = 9,600,000 bytes (~9.6 MB)
MAX_AUDIO_BUFFER_BYTES = 9_600_000


class SessionConnectionManager:
    """Manages active WebSockets keyed by session ID with support for reconnects."""

    def __init__(self) -> None:
        self._active_connections: Dict[str, WebSocket] = {}
        self._audio_buffers: Dict[str, bytearray] = {}
        self._repeat_counts: Dict[str, Dict[str, int]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept WebSocket connection and register session."""
        await websocket.accept()
        async with self._lock:
            # If an existing socket is present, close the older one gracefully
            if session_id in self._active_connections:
                old_ws = self._active_connections[session_id]
                try:
                    await old_ws.close(code=1000, reason="Replaced by new connection")
                except Exception:
                    pass
            self._active_connections[session_id] = websocket
            if session_id not in self._audio_buffers:
                self._audio_buffers[session_id] = bytearray()
            if session_id not in self._repeat_counts:
                self._repeat_counts[session_id] = {}
        logger.info(f"WebSocket client connected for viva session '{session_id}'")

    async def disconnect(self, session_id: str) -> None:
        """Remove WebSocket connection and clean up session buffers on departure."""
        async with self._lock:
            if session_id in self._active_connections:
                del self._active_connections[session_id]
            if session_id in self._audio_buffers:
                del self._audio_buffers[session_id]
            if session_id in self._repeat_counts:
                del self._repeat_counts[session_id]
        logger.info(f"WebSocket client disconnected for viva session '{session_id}'")

    async def send_json(self, session_id: str, message: dict) -> bool:
        """Send JSON message to the connected student with backpressure check."""
        ws = self._active_connections.get(session_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send JSON message to session '{session_id}': {e}")
            return False

    def append_audio_chunk(self, session_id: str, chunk: bytes) -> None:
        """Append streamed candidate audio bytes to session buffer with size cap enforcement."""
        if session_id not in self._audio_buffers:
            self._audio_buffers[session_id] = bytearray()
        
        current_len = len(self._audio_buffers[session_id])
        if current_len + len(chunk) > MAX_AUDIO_BUFFER_BYTES:
            raise BufferError("AUDIO_BUFFER_OVERFLOW")
        
        self._audio_buffers[session_id].extend(chunk)

    def consume_audio_buffer(self, session_id: str) -> bytes:
        """Retrieve and clear candidate audio buffer."""
        buf = self._audio_buffers.get(session_id, bytearray())
        audio_data = bytes(buf)
        self._audio_buffers[session_id] = bytearray()
        return audio_data

    def get_repeat_count(self, session_id: str, turn_id: str) -> int:
        """Get number of times a question repeat was requested for turn."""
        return self._repeat_counts.get(session_id, {}).get(turn_id, 0)

    def increment_repeat_count(self, session_id: str, turn_id: str) -> int:
        """Increment and return the repeat count for a turn."""
        if session_id not in self._repeat_counts:
            self._repeat_counts[session_id] = {}
        count = self._repeat_counts[session_id].get(turn_id, 0) + 1
        self._repeat_counts[session_id][turn_id] = count
        return count


manager = SessionConnectionManager()


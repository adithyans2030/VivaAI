"""WebSocket connection manager for handling active viva sessions and backpressure."""

import asyncio
from typing import Dict, Optional, Set
from fastapi import WebSocket

from app.core.logging import logger


class SessionConnectionManager:
    """Manages active WebSockets keyed by session ID with support for reconnects."""

    def __init__(self) -> None:
        self._active_connections: Dict[str, WebSocket] = {}
        self._audio_buffers: Dict[str, bytearray] = {}
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
        logger.info(f"WebSocket client connected for viva session '{session_id}'")

    async def disconnect(self, session_id: str) -> None:
        """Remove WebSocket connection on client departure."""
        async with self._lock:
            if session_id in self._active_connections:
                del self._active_connections[session_id]
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
        """Append streamed candidate audio bytes to session buffer."""
        if session_id not in self._audio_buffers:
            self._audio_buffers[session_id] = bytearray()
        self._audio_buffers[session_id].extend(chunk)

    def consume_audio_buffer(self, session_id: str) -> bytes:
        """Retrieve and clear candidate audio buffer."""
        buf = self._audio_buffers.get(session_id, bytearray())
        audio_data = bytes(buf)
        self._audio_buffers[session_id] = bytearray()
        return audio_data


manager = SessionConnectionManager()

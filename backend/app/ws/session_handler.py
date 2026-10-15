"""WebSocket endpoint handler for viva voce examination sessions."""

import base64
from pathlib import Path
import time
from typing import Optional
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import logger
from app.core.security import decode_token
from app.models.session import SessionStatus, VivaSession
from app.models.turn import Turn
from app.models.user import User
from app.services.stt import get_stt_provider
from app.services.tts import get_tts_provider
from app.ws.connection_manager import manager
from app.ws.protocol import (
    AudioChunkPayload,
    FeedbackPayload,
    QuestionPayload,
    SessionCompletePayload,
    SpeechEndPayload,
    StateChangePayload,
    TranscriptPayload,
)

router = APIRouter(tags=["websocket"])


async def authenticate_ws(websocket: WebSocket, token: str) -> Optional[User]:
    """Validate JWT token during WebSocket handshake."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            return None
        async with async_session_factory() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user and user.is_active:
                return user
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
    return None


@router.websocket("/ws/sessions/{session_id}")
async def viva_session_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """Real-time voice viva session WebSocket endpoint."""
    user = await authenticate_ws(websocket, token)
    if not user:
        await websocket.close(code=4401, reason="Authentication failed")
        return

    # Verify session and consent
    async with async_session_factory() as db:
        stmt = (
            select(VivaSession)
            .where(VivaSession.id == session_id)
            .options(selectinload(VivaSession.turns))
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if not session:
            await websocket.close(code=4404, reason="Session not found")
            return

        if session.student_id != user.id and user.role.value != "admin":
            await websocket.close(code=4403, reason="Access denied to session")
            return

        if not session.recording_consent:
            await websocket.close(
                code=4403,
                reason="Recording consent is required before initiating audio stream",
            )
            return

        # Transition status to in_progress if just created
        if session.status == SessionStatus.CREATED:
            session.status = SessionStatus.IN_PROGRESS
            await db.commit()

    await manager.connect(session_id, websocket)

    # Prepare audio output directory for this session
    session_audio_dir = settings.AUDIO_STORAGE_PATH / session_id
    session_audio_dir.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "payload": {"timestamp": int(time.time())}})

            elif msg_type == "audio_chunk":
                chunk_b64 = payload.get("audio_b64", "")
                if chunk_b64:
                    raw_bytes = base64.b64decode(chunk_b64)
                    manager.append_audio_chunk(session_id, raw_bytes)

            elif msg_type == "speech_end":
                turn_id = payload.get("turn_id", str(uuid.uuid4()))
                # Retrieve buffered audio bytes
                audio_bytes = manager.consume_audio_buffer(session_id)

                # Persist raw candidate audio file to disk
                audio_path = session_audio_dir / f"{turn_id}.wav"
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)

                # Signal processing state
                await manager.send_json(
                    session_id,
                    {
                        "type": "state_change",
                        "payload": {"state": "processing", "turn_number": 1},
                    },
                )

                # Execute STT transcription with word-level timestamps
                stt_service = get_stt_provider()
                stt_result = await stt_service.transcribe(audio_bytes if audio_bytes else audio_path)

                # Broadcast transcript event to student UI
                await manager.send_json(
                    session_id,
                    {
                        "type": "transcript",
                        "payload": {
                            "turn_id": turn_id,
                            "text": stt_result.text,
                            "words": [w.model_dump() for w in stt_result.words],
                        },
                    },
                )

                # Save transcript & turn metrics in database
                async with async_session_factory() as db:
                    turn_stmt = select(Turn).where(Turn.id == turn_id)
                    turn = (await db.execute(turn_stmt)).scalar_one_or_none()
                    if turn:
                        turn.transcript = stt_result.text
                        turn.word_timestamps = [w.model_dump() for w in stt_result.words]
                        turn.student_audio_path = str(audio_path)
                        turn.audio_duration_seconds = stt_result.duration_seconds
                        await db.commit()

            elif msg_type == "repeat_question":
                turn_id = payload.get("turn_id")
                await manager.send_json(
                    session_id,
                    {
                        "type": "state_change",
                        "payload": {"state": "examiner_speaking", "turn_number": 1},
                    },
                )

            elif msg_type == "end_session":
                async with async_session_factory() as db:
                    sess_stmt = select(VivaSession).where(VivaSession.id == session_id)
                    active_sess = (await db.execute(sess_stmt)).scalar_one_or_none()
                    if active_sess:
                        active_sess.status = SessionStatus.COMPLETED
                        await db.commit()

                await manager.send_json(
                    session_id,
                    {
                        "type": "session_complete",
                        "payload": {
                            "session_id": session_id,
                            "total_score": 8.5,
                            "overall_authenticity": "low",
                            "turns_count": 4,
                        },
                    },
                )
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly: session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}")
        await manager.send_json(
            session_id,
            {"type": "error", "payload": {"code": "WS_ERROR", "message": str(e)}},
        )
    finally:
        await manager.disconnect(session_id)

"""WebSocket endpoint handler for viva voce examination sessions."""

import asyncio
import base64
import time
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import logger
from app.core.security import decode_token
from app.models.session import SessionStatus, VivaSession
from app.models.turn import Turn
from app.models.user import User
from app.services.audio_conversion import transcode_to_wav
from app.services.session_state import get_viva_orchestrator
from app.services.stt import get_stt_provider
from app.services.tts import get_tts_provider
from app.ws.connection_manager import manager

router = APIRouter(tags=["websocket"])

IDLE_TIMEOUT_SECONDS = 60.0


async def authenticate_ws(
    websocket: WebSocket, session_id: str, ticket: Optional[str] = None, token: Optional[str] = None
) -> Optional[User]:
    """Validate single-use WebSocket ticket (preferred) or fallback JWT token during handshake."""
    from app.core.security import consume_ws_ticket

    user_id = None
    if ticket:
        try:
            record = consume_ws_ticket(ticket, session_id)
            user_id = record["user_id"]
        except Exception as e:
            logger.warning(f"WebSocket ticket auth failed for session {session_id}: {e}")
            return None
    elif token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id or payload.get("type") != "access":
                return None
        except Exception as e:
            logger.warning(f"WebSocket JWT auth failed: {e}")
            return None
    else:
        return None

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user and user.is_active:
            return user
    return None


@router.websocket("/ws/sessions/{session_id}")
async def viva_session_websocket(
    websocket: WebSocket,
    session_id: str,
    ticket: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
):
    """Real-time voice viva session WebSocket endpoint supporting tickets, reconnects, and streaming."""
    user = await authenticate_ws(websocket, session_id, ticket=ticket, token=token)
    if not user:
        await websocket.close(code=4401, reason="Authentication failed: invalid or expired ticket/token")
        return

    # Verify session ownership and consent
    async with async_session_factory() as db:
        stmt = select(VivaSession).where(VivaSession.id == session_id).options(selectinload(VivaSession.turns))
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

    # Reconnection handling (WS-4): Send current recovery state immediately so client resumes without restart
    orchestrator = get_viva_orchestrator()
    async with async_session_factory() as db:
        recovery_state = await orchestrator.get_recovery_state(db, session_id)
        await manager.send_json(session_id, {"type": "session_state", "payload": recovery_state})

    # Prepare audio output directory for this session
    session_audio_dir = settings.AUDIO_STORAGE_PATH / session_id
    session_audio_dir.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            try:
                # Heartbeat keepalive: terminate orphaned connections after 60 seconds of client silence
                data = await asyncio.wait_for(websocket.receive_json(), timeout=IDLE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.info(f"WebSocket session {session_id} timed out after {IDLE_TIMEOUT_SECONDS}s of silence")
                await websocket.close(code=1000, reason="Idle timeout reached")
                break

            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "payload": {"timestamp": int(time.time())}})

            elif msg_type == "audio_chunk":
                chunk_b64 = payload.get("audio_b64", "")
                if chunk_b64:
                    try:
                        raw_bytes = base64.b64decode(chunk_b64, validate=True)
                    except Exception:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "error",
                                "payload": {
                                    "code": "INVALID_AUDIO_ENCODING",
                                    "message": "Malformed base64 audio chunk received",
                                },
                            },
                        )
                        continue

                    try:
                        manager.append_audio_chunk(session_id, raw_bytes)
                    except BufferError:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "error",
                                "payload": {
                                    "code": "AUDIO_BUFFER_OVERFLOW",
                                    "message": "Audio buffer exceeds maximum limit (5 minutes of 16kHz audio)",
                                },
                            },
                        )

            elif msg_type == "speech_end":
                turn_id = payload.get("turn_id")
                if not turn_id:
                    await manager.send_json(
                        session_id,
                        {
                            "type": "error",
                            "payload": {"code": "INVALID_TURN", "message": "Missing turn_id in speech_end payload"},
                        },
                    )
                    continue

                # Validate turn existence in DB (Reject unknown turn_id without creating dummy turns)
                async with async_session_factory() as db:
                    turn_stmt = select(Turn).where(Turn.id == turn_id, Turn.session_id == session_id)
                    existing_turn = (await db.execute(turn_stmt)).scalar_one_or_none()
                    if not existing_turn:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "error",
                                "payload": {
                                    "code": "INVALID_TURN",
                                    "message": f"Turn '{turn_id}' does not exist for session",
                                },
                            },
                        )
                        continue
                    active_turn_number = existing_turn.turn_number

                # Retrieve buffered audio bytes and validate non-empty
                audio_bytes = manager.consume_audio_buffer(session_id)
                if not audio_bytes or len(audio_bytes.strip()) < 100:
                    await manager.send_json(
                        session_id,
                        {
                            "type": "error",
                            "payload": {
                                "code": "EMPTY_AUDIO",
                                "message": "No audio received. Please speak your answer clearly.",
                            },
                        },
                    )
                    # Re-transition to listening state so student can try speaking again
                    await manager.send_json(
                        session_id,
                        {
                            "type": "state_change",
                            "payload": {"state": "listening", "turn_number": active_turn_number},
                        },
                    )
                    continue

                # Signal processing state with dynamic turn number derived from DB
                await manager.send_json(
                    session_id,
                    {
                        "type": "state_change",
                        "payload": {"state": "processing", "turn_number": active_turn_number},
                    },
                )

                # Persist raw/transcoded audio asynchronously (non-blocking file write & ffmpeg)
                audio_path = session_audio_dir / f"{turn_id}.wav"
                await transcode_to_wav(audio_bytes, audio_path)

                # Execute STT transcription (offloaded to thread inside provider)
                stt_service = get_stt_provider()
                try:
                    stt_result = await stt_service.transcribe(audio_path)
                except Exception as e:
                    logger.error(f"STT transcription failed for turn {turn_id}: {e}")
                    await manager.send_json(
                        session_id,
                        {
                            "type": "error",
                            "payload": {
                                "code": "STT_FAILED",
                                "message": "Speech transcription failed. Please repeat your answer.",
                            },
                        },
                    )
                    await manager.send_json(
                        session_id,
                        {
                            "type": "state_change",
                            "payload": {"state": "listening", "turn_number": active_turn_number},
                        },
                    )
                    continue

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

                # Execute AI Grader & Advisory Authenticity assessment
                async with async_session_factory() as db:
                    turn, grade_res, auth_report = await orchestrator.evaluate_turn_submission(
                        db=db,
                        session_id=session_id,
                        turn_id=turn_id,
                        student_transcript=stt_result.text,
                        word_timestamps=[w.model_dump() for w in stt_result.words],
                        audio_path=str(audio_path),
                        audio_duration_seconds=stt_result.duration_seconds,
                        onset_latency_seconds=payload.get("onset_latency_seconds"),
                    )

                # Dispatch feedback event to student UI
                await manager.send_json(
                    session_id,
                    {
                        "type": "feedback",
                        "payload": {
                            "turn_id": turn_id,
                            "score_0_10": grade_res.score_0_10,
                            "feedback": grade_res.feedback,
                            "rubric": grade_res.rubric.model_dump(),
                            "authenticity": {
                                "likelihood": auth_report.likelihood.value,
                                "confidence": auth_report.confidence,
                                "reasons": auth_report.reasons,
                                "is_advisory": True,
                                "disclaimer": auth_report.disclaimer,
                            },
                        },
                    },
                )

            elif msg_type in ("ready", "request_question"):
                async with async_session_factory() as db:
                    active_turn, is_done = await orchestrator.get_or_create_next_question(db, session_id)
                    if is_done or not active_turn:
                        sess_stmt = (
                            select(VivaSession)
                            .where(VivaSession.id == session_id)
                            .options(selectinload(VivaSession.turns), selectinload(VivaSession.subject))
                        )
                        sess = (await db.execute(sess_stmt)).scalar_one_or_none()
                        if sess is None:
                            await manager.send_json(
                                session_id,
                                {
                                    "type": "error",
                                    "payload": {"code": "SESSION_NOT_FOUND", "message": "Session no longer exists."},
                                },
                            )
                            break
                        report = await orchestrator.finalize_session(db, sess)
                        await manager.send_json(session_id, {"type": "session_complete", "payload": report})
                        break
                    else:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "state_change",
                                "payload": {"state": "examiner_speaking", "turn_number": active_turn.turn_number},
                            },
                        )
                        # Server-side TTS synthesis (WS-7: EdgeTTS / Piper / Mock / Browser)
                        tts_service = get_tts_provider()
                        tts_audio = await tts_service.synthesize_audio(active_turn.question_text)
                        audio_b64 = base64.b64encode(tts_audio).decode("utf-8") if tts_audio else None

                        await manager.send_json(
                            session_id,
                            {
                                "type": "question",
                                "payload": {
                                    "turn_id": active_turn.id,
                                    "turn_number": active_turn.turn_number,
                                    "question_text": active_turn.question_text,
                                    "topic": active_turn.topic,
                                    "question_type": active_turn.question_type,
                                    "audio_b64": audio_b64,
                                },
                            },
                        )
                        await manager.send_json(
                            session_id,
                            {
                                "type": "state_change",
                                "payload": {"state": "listening", "turn_number": active_turn.turn_number},
                            },
                        )

            elif msg_type == "repeat_question":
                turn_id = payload.get("turn_id")
                async with async_session_factory() as db:
                    turn_stmt = select(Turn).where(Turn.id == turn_id, Turn.session_id == session_id)
                    repeat_turn = (await db.execute(turn_stmt)).scalar_one_or_none()
                    if not repeat_turn:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "error",
                                "payload": {"code": "INVALID_TURN", "message": "Turn not found to repeat."},
                            },
                        )
                        continue

                    repeat_count = manager.get_repeat_count(session_id, repeat_turn.id)
                    if repeat_count >= 1:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "error",
                                "payload": {
                                    "code": "REPEAT_LIMIT_EXCEEDED",
                                    "message": "Question repeat limit reached for this turn (maximum 1 repeat).",
                                },
                            },
                        )
                        continue

                    manager.increment_repeat_count(session_id, repeat_turn.id)
                    await manager.send_json(
                        session_id,
                        {
                            "type": "state_change",
                            "payload": {"state": "examiner_speaking", "turn_number": repeat_turn.turn_number},
                        },
                    )

                    # Re-trigger server TTS on repeat
                    tts_service = get_tts_provider()
                    tts_audio = await tts_service.synthesize_audio(repeat_turn.question_text)
                    audio_b64 = base64.b64encode(tts_audio).decode("utf-8") if tts_audio else None

                    await manager.send_json(
                        session_id,
                        {
                            "type": "question",
                            "payload": {
                                "turn_id": repeat_turn.id,
                                "turn_number": repeat_turn.turn_number,
                                "question_text": repeat_turn.question_text,
                                "topic": repeat_turn.topic,
                                "question_type": repeat_turn.question_type,
                                "is_repeat": True,
                                "audio_b64": audio_b64,
                            },
                        },
                    )
                    await manager.send_json(
                        session_id,
                        {
                            "type": "state_change",
                            "payload": {"state": "listening", "turn_number": repeat_turn.turn_number},
                        },
                    )

            elif msg_type == "end_session":
                async with async_session_factory() as db:
                    sess_stmt = (
                        select(VivaSession)
                        .where(VivaSession.id == session_id)
                        .options(
                            selectinload(VivaSession.turns),
                            selectinload(VivaSession.subject),
                        )
                    )
                    active_sess = (await db.execute(sess_stmt)).scalar_one_or_none()
                    if not active_sess:
                        await manager.send_json(
                            session_id,
                            {
                                "type": "error",
                                "payload": {"code": "SESSION_NOT_FOUND", "message": "Session not found."},
                            },
                        )
                        break

                    report = await orchestrator.finalize_session(db, active_sess)

                await manager.send_json(
                    session_id,
                    {
                        "type": "session_complete",
                        "payload": report,
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

"""Typed Pydantic WebSocket event protocol."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

from app.services.stt import STTWord

# Client Event Types
ClientEventType = Literal["audio_chunk", "speech_end", "repeat_question", "end_session", "ping"]

# Server Event Types
ServerEventType = Literal[
    "state_change",
    "question",
    "tts_audio",
    "transcript",
    "feedback",
    "session_complete",
    "error",
    "pong",
]


class BaseWSMessage(BaseModel):
    type: str
    payload: Dict[str, Any] = {}


# --- Client Payloads ---
class AudioChunkPayload(BaseModel):
    turn_id: str
    chunk_index: int = 0
    audio_b64: str


class SpeechEndPayload(BaseModel):
    turn_id: str
    duration_ms: Optional[int] = None


class RepeatQuestionPayload(BaseModel):
    turn_id: str


class PingPayload(BaseModel):
    timestamp: int


# --- Server Payloads ---
class StateChangePayload(BaseModel):
    state: Literal["idle", "examiner_speaking", "listening", "processing", "completed"]
    turn_number: int


class QuestionPayload(BaseModel):
    turn_id: str
    turn_number: int
    topic: str
    question_type: str
    question_text: str
    prompt_version: str = "v1.0"
    source_references: Optional[List[Dict[str, Any]]] = None


class TTSAudioPayload(BaseModel):
    turn_id: str
    chunk_index: int
    audio_b64: str
    is_last: bool = False


class TranscriptPayload(BaseModel):
    turn_id: str
    text: str
    words: List[STTWord] = []


class FeedbackPayload(BaseModel):
    turn_id: str
    score_0_10: float
    feedback: str
    rubric: Dict[str, Any]


class SessionCompletePayload(BaseModel):
    session_id: str
    total_score: float
    overall_authenticity: str
    turns_count: int


class ErrorPayload(BaseModel):
    code: str
    message: str

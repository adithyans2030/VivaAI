"""Teacher Report and Override Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.session import AuthenticityLikelihood
from app.schemas.turn import TurnResponse


class TeacherOverrideRequest(BaseModel):
    turn_id: Optional[str] = None
    new_score: float = Field(..., ge=0.0, le=10.0)
    new_authenticity: Optional[AuthenticityLikelihood] = None
    reason: str = Field(..., min_length=5, max_length=1000)


class TeacherNoteUpdate(BaseModel):
    teacher_notes: str = Field(..., max_length=5000)


class SessionReport(BaseModel):
    session_id: str
    subject_id: str
    subject_name: str
    student_id: str
    student_name: str
    date: datetime
    total_score: Optional[float]
    authenticity_likelihood: AuthenticityLikelihood
    authenticity_confidence: Optional[float]
    authenticity_reasons: List[str]
    teacher_notes: Optional[str]
    turns: List[TurnResponse]
    analytics: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class ClassAnalyticsSummary(BaseModel):
    subject_id: str
    total_sessions: int
    average_score: float
    score_distribution: Dict[str, int]
    flagged_authenticity_count: int
    weak_topics: List[Dict[str, Any]]

"""VivaSession Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.session import AuthenticityLikelihood, SessionStatus
from app.schemas.turn import TurnResponse


class SessionCreate(BaseModel):
    subject_id: str


class ConsentUpdate(BaseModel):
    recording_consent: bool = Field(..., description="Student consent to record audio for viva")


class SessionResponse(BaseModel):
    id: str
    student_id: str
    subject_id: str
    status: SessionStatus
    recording_consent: bool
    total_score: Optional[float] = None
    overall_authenticity_likelihood: AuthenticityLikelihood
    overall_authenticity_confidence: Optional[float] = None
    overall_authenticity_reasons: Optional[List[str]] = None
    teacher_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionListItem(SessionResponse):
    """Session row for dashboards: includes display names so lists need no extra lookups."""

    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    student_name: Optional[str] = None


class SessionDetailResponse(SessionListItem):
    turns: List[TurnResponse] = []
    final_report: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

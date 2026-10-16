"""Turn and Evaluation Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.session import AuthenticityLikelihood


class RubricBreakdown(BaseModel):
    correctness: float = Field(..., ge=0.0, le=10.0)
    completeness: float = Field(..., ge=0.0, le=10.0)
    clarity: float = Field(..., ge=0.0, le=10.0)
    depth: float = Field(..., ge=0.0, le=10.0)
    missing_points: List[str] = []
    incorrect_claims: List[str] = []


class GraderResult(BaseModel):
    score_0_10: float = Field(..., ge=0.0, le=10.0)
    rubric: RubricBreakdown
    feedback: str
    followup_needed: bool = False
    followup_type: Optional[str] = None


class AuthenticityResult(BaseModel):
    likelihood: AuthenticityLikelihood = AuthenticityLikelihood.UNKNOWN
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reasons: List[str] = []
    metrics: Dict[str, Any] = {}
    is_advisory: bool = True
    disclaimer: str = "Advisory signal to support teacher judgment — not an automated accusation."


class TurnResponse(BaseModel):
    id: str
    session_id: str
    turn_number: int
    question_text: str
    question_type: str
    topic: str
    source_references: Optional[List[Dict[str, Any]]] = None
    prompt_version: str
    student_audio_path: Optional[str] = None
    audio_duration_seconds: Optional[float] = None
    transcript: Optional[str] = None
    word_timestamps: Optional[List[Dict[str, Any]]] = None
    score_0_10: Optional[float] = None
    rubric_breakdown: Optional[Dict[str, Any]] = None
    feedback: Optional[str] = None
    followup_needed: bool = False
    followup_type: Optional[str] = None
    authenticity_likelihood: AuthenticityLikelihood
    authenticity_confidence: Optional[float] = None
    authenticity_reasons: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

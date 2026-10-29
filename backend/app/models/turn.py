"""Turn model representing a single viva question/answer interaction."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.session import AuthenticityLikelihood

if TYPE_CHECKING:
    from app.models.session import VivaSession


class Turn(Base):
    __tablename__ = "turns"

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("viva_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Question details
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), default="conceptual", nullable=False)
    topic: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_references: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)

    # Student answer and audio
    student_audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    audio_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_timestamps: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Grader evaluation
    score_0_10: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rubric_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    followup_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    followup_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Authenticity analysis
    authenticity_likelihood: Mapped[AuthenticityLikelihood] = mapped_column(
        SQLEnum(AuthenticityLikelihood),
        default=AuthenticityLikelihood.UNKNOWN,
        nullable=False,
    )
    authenticity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    authenticity_reasons: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    speech_features: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    session: Mapped["VivaSession"] = relationship("VivaSession", back_populates="turns")

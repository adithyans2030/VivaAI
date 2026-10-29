"""VivaSession model."""

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.audit import ScoreOverride
    from app.models.subject import Subject
    from app.models.turn import Turn
    from app.models.user import User


class SessionStatus(str, Enum):
    CREATED = "created"
    WARMUP = "warmup"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AuthenticityLikelihood(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class VivaSession(Base):
    __tablename__ = "viva_sessions"

    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus),
        default=SessionStatus.CREATED,
        nullable=False,
        index=True,
    )
    recording_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Baseline acoustic / speech metrics captured during warmup
    warmup_baseline: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Aggregated results
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_authenticity_likelihood: Mapped[AuthenticityLikelihood] = mapped_column(
        SQLEnum(AuthenticityLikelihood),
        default=AuthenticityLikelihood.UNKNOWN,
        nullable=False,
    )
    overall_authenticity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_authenticity_reasons: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Teacher review & overrides
    teacher_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    student: Mapped["User"] = relationship("User", back_populates="viva_sessions")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="sessions")
    turns: Mapped[List["Turn"]] = relationship(
        "Turn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Turn.turn_number",
    )
    score_overrides: Mapped[List["ScoreOverride"]] = relationship(
        "ScoreOverride",
        back_populates="session",
        cascade="all, delete-orphan",
    )

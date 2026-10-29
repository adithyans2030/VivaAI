"""Audit logging and score override models."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.session import VivaSession


class AuditLog(Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ScoreOverride(Base):
    __tablename__ = "score_overrides"

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("viva_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    teacher_id: Mapped[str] = mapped_column(String(36), nullable=False)
    original_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    original_authenticity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_authenticity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    session: Mapped["VivaSession"] = relationship("VivaSession", back_populates="score_overrides")

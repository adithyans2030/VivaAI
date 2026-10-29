"""Subject model."""

from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.session import VivaSession
    from app.models.user import User


class Subject(Base):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    teacher_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    teacher: Mapped["User"] = relationship("User", back_populates="created_subjects")
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="subject",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[List["VivaSession"]] = relationship(
        "VivaSession",
        back_populates="subject",
        cascade="all, delete-orphan",
    )

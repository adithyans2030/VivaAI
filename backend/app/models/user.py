"""User model."""

from enum import Enum
from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, Enum as SQLEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.subject import Subject
    from app.models.session import VivaSession


class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.STUDENT,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    created_subjects: Mapped[List["Subject"]] = relationship(
        "Subject",
        back_populates="teacher",
        cascade="all, delete-orphan",
    )
    viva_sessions: Mapped[List["VivaSession"]] = relationship(
        "VivaSession",
        back_populates="student",
        cascade="all, delete-orphan",
    )

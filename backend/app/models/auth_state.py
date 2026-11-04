"""Persistent auth state: revoked refresh tokens, WebSocket tickets and rate-limit events.

Kept in the database (not process memory) so revocations survive restarts and are shared
by every worker. Times are Unix epoch seconds to keep comparisons portable across SQLite
and PostgreSQL.
"""

from typing import Optional

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    # Unique, so inserting the same jti twice fails: that is what makes refresh rotation single-use.
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)


class WsTicket(Base):
    __tablename__ = "ws_tickets"

    ticket: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    used_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    at: Mapped[float] = mapped_column(Float, index=True, nullable=False)

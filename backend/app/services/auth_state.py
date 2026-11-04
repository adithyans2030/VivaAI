"""Database-backed refresh-token revocation, single-use WebSocket tickets and rate limiting."""

import secrets
import time
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_state import RateLimitEvent, RevokedToken, WsTicket

TICKET_TTL_SECONDS = 30


@dataclass(frozen=True)
class TicketGrant:
    session_id: str
    user_id: str
    role: str


# --------------------------------------------------------------------------- refresh tokens


async def revoke_once(db: AsyncSession, jti: str, expires_at: float) -> bool:
    """Revoke a token id. Returns False if it was already revoked (i.e. this is a replay).

    Relies on the unique constraint, so two concurrent refreshes with the same token
    cannot both succeed.
    """
    db.add(RevokedToken(jti=jti, expires_at=expires_at))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False
    return True


async def is_revoked(db: AsyncSession, jti: str) -> bool:
    return (await db.execute(select(RevokedToken.id).where(RevokedToken.jti == jti))).first() is not None


# --------------------------------------------------------------------------- WebSocket tickets


async def issue_ticket(db: AsyncSession, session_id: str, user_id: str, role: str) -> str:
    ticket = f"wst_{secrets.token_urlsafe(32)}"
    db.add(
        WsTicket(
            ticket=ticket,
            session_id=session_id,
            user_id=user_id,
            role=role,
            expires_at=time.time() + TICKET_TTL_SECONDS,
        )
    )
    await db.flush()
    return ticket


async def consume_ticket(db: AsyncSession, ticket: str, session_id: str) -> TicketGrant:
    """Atomically mark a ticket used. Raises ValueError explaining why it was refused."""
    now = time.time()
    result = await db.execute(
        update(WsTicket)
        .where(
            WsTicket.ticket == ticket,
            WsTicket.session_id == session_id,
            WsTicket.used_at.is_(None),
            WsTicket.expires_at > now,
        )
        .values(used_at=now)
    )
    record = (await db.execute(select(WsTicket).where(WsTicket.ticket == ticket))).scalar_one_or_none()
    await db.commit()

    if result.rowcount == 1 and record is not None:  # type: ignore[attr-defined]
        return TicketGrant(session_id=record.session_id, user_id=record.user_id, role=record.role)
    if record is None:
        raise ValueError("Invalid or unknown WebSocket ticket")
    if record.session_id != session_id:
        raise ValueError("WebSocket ticket does not match the requested viva session")
    if record.used_at is not None:
        raise ValueError("WebSocket ticket has already been used")
    raise ValueError("WebSocket ticket has expired")


# --------------------------------------------------------------------------- rate limiting


async def allow_request(db: AsyncSession, key: str, max_requests: int, window_seconds: int) -> bool:
    """Sliding-window limiter shared by all workers. Records the attempt when allowed."""
    now = time.time()
    await db.execute(delete(RateLimitEvent).where(RateLimitEvent.key == key, RateLimitEvent.at <= now - window_seconds))
    count = (await db.execute(select(func.count()).where(RateLimitEvent.key == key))).scalar_one()
    if count >= max_requests:
        await db.commit()
        return False
    db.add(RateLimitEvent(key=key, at=now))
    await db.commit()
    return True


# --------------------------------------------------------------------------- housekeeping


async def purge_expired(db: AsyncSession) -> None:
    """Drop rows that can no longer matter (called by the daily maintenance sweep)."""
    now = time.time()
    await db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
    await db.execute(delete(WsTicket).where(WsTicket.expires_at < now - 3600))
    await db.execute(delete(RateLimitEvent).where(RateLimitEvent.at < now - 86400))
    await db.commit()

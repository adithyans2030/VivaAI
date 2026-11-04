"""Persistent auth state: revocation, tickets and rate limits live in the DB, not one process."""

import asyncio
import time

import pytest
from sqlalchemy import func, select

from app.models.auth_state import RateLimitEvent, RevokedToken, WsTicket
from app.services import auth_state
from tests.conftest import test_async_session


async def test_revocation_is_visible_from_any_db_session() -> None:
    # Separate sessions stand in for a restarted process or another worker.
    async with test_async_session() as db:
        assert await auth_state.revoke_once(db, "jti-1", time.time() + 60)
        await db.commit()
    async with test_async_session() as db:
        assert await auth_state.is_revoked(db, "jti-1")
        assert not await auth_state.revoke_once(db, "jti-1", time.time() + 60)


async def test_concurrent_refreshes_with_one_token_only_one_wins(client, student_user) -> None:
    login = await client.post("/api/v1/auth/login", data={"username": "student@vivaiq.edu", "password": "student123"})
    refresh = login.json()["refresh_token"]

    async def attempt() -> int:
        async with test_async_session() as db:
            ok = await auth_state.revoke_once(db, refresh[-40:], time.time() + 60)
            await db.commit()
            return int(ok)

    assert sum(await asyncio.gather(*[attempt() for _ in range(5)])) == 1


async def test_rate_limit_is_shared_across_sessions() -> None:
    results = []
    for _ in range(4):
        async with test_async_session() as db:
            results.append(await auth_state.allow_request(db, "login_1.2.3.4_x", max_requests=3, window_seconds=60))
    assert results == [True, True, True, False]


async def test_rate_limit_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(auth_state.time, "time", lambda: now[0])
    async with test_async_session() as db:
        assert await auth_state.allow_request(db, "k", max_requests=1, window_seconds=60)
        assert not await auth_state.allow_request(db, "k", max_requests=1, window_seconds=60)
        now[0] += 61
        assert await auth_state.allow_request(db, "k", max_requests=1, window_seconds=60)


async def test_expired_ticket_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(auth_state.time, "time", lambda: now[0])
    async with test_async_session() as db:
        ticket = await auth_state.issue_ticket(db, "sess-1", "user-1", "student")
        await db.commit()
    now[0] += auth_state.TICKET_TTL_SECONDS + 1
    async with test_async_session() as db:
        with pytest.raises(ValueError, match="expired"):
            await auth_state.consume_ticket(db, ticket, "sess-1")
        with pytest.raises(ValueError, match="unknown"):
            await auth_state.consume_ticket(db, "wst_nope", "sess-1")


async def test_purge_drops_only_stale_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    now = time.time()
    async with test_async_session() as db:
        db.add_all(
            [
                RevokedToken(jti="old", expires_at=now - 1),
                RevokedToken(jti="live", expires_at=now + 3600),
                WsTicket(ticket="t-old", session_id="s", user_id="u", role="student", expires_at=now - 7200),
                WsTicket(ticket="t-new", session_id="s", user_id="u", role="student", expires_at=now + 30),
                RateLimitEvent(key="k", at=now - 2 * 86400),
                RateLimitEvent(key="k", at=now),
            ]
        )
        await db.commit()
        await auth_state.purge_expired(db)
        jtis = (await db.execute(select(RevokedToken.jti))).scalars().all()
        tickets = (await db.execute(select(WsTicket.ticket))).scalars().all()
        events = (await db.execute(select(func.count()).select_from(RateLimitEvent))).scalar_one()
    assert jtis == ["live"] and tickets == ["t-new"] and events == 1

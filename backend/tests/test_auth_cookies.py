"""Browser session: httpOnly cookies, CSRF header rule, cookie refresh/logout, ticket-only WebSocket."""

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.auth_cookies import ACCESS_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from app.core.security import create_access_token
from app.main import app
from app.models.user import User

CSRF = {CSRF_HEADER: "1"}


async def _login(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", data={"username": "student@vivaiq.edu", "password": "student123"})
    assert resp.status_code == 200
    return resp


async def test_login_sets_httponly_cookies_scoped_to_the_api(client: AsyncClient, student_user: User) -> None:
    resp = await _login(client)
    set_cookies = resp.headers.get_list("set-cookie")
    access = next(c for c in set_cookies if c.startswith(f"{ACCESS_COOKIE}="))
    refresh = next(c for c in set_cookies if c.startswith(f"{REFRESH_COOKIE}="))
    for cookie in (access, refresh):
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
    assert "Path=/api/v1;" in access or access.endswith("Path=/api/v1")
    # The refresh token is only ever sent to the auth routes.
    assert "Path=/api/v1/auth" in refresh


async def test_cookie_authenticates_reads_without_any_header(client: AsyncClient, student_user: User) -> None:
    await _login(client)
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "student@vivaiq.edu"


async def test_cookie_write_without_csrf_header_is_refused(client: AsyncClient, student_user: User) -> None:
    await _login(client)
    body = {"subject_id": "does-not-matter"}
    refused = await client.post("/api/v1/sessions", json=body)
    assert refused.status_code == 403
    assert CSRF_HEADER in refused.json()["detail"]

    # With the header the request is authenticated and reaches the route (404: no such subject).
    allowed = await client.post("/api/v1/sessions", json=body, headers=CSRF)
    assert allowed.status_code != 403


async def test_bearer_requests_need_no_csrf_header(client: AsyncClient, student_user: User) -> None:
    token = (await _login(client)).json()["access_token"]
    client.cookies.clear()
    resp = await client.post("/api/v1/sessions", json={"subject_id": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code != 403


async def test_cookie_refresh_rotates_and_never_returns_tokens(client: AsyncClient, student_user: User) -> None:
    await _login(client)
    old_refresh = client.cookies.get(REFRESH_COOKIE)

    assert (await client.post("/api/v1/auth/refresh")).status_code == 403  # no CSRF header

    resp = await client.post("/api/v1/auth/refresh", headers=CSRF)
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" not in body and "refresh_token" not in body
    assert body["expires_in"] > 0
    new_refresh = client.cookies.get(REFRESH_COOKIE)
    assert new_refresh and new_refresh != old_refresh

    # The old refresh token was revoked by the rotation.
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


async def test_body_refresh_still_returns_tokens_for_api_clients(client: AsyncClient, student_user: User) -> None:
    refresh = (await _login(client)).json()["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert resp.json()["access_token"] and resp.json()["refresh_token"]


async def test_logout_revokes_refresh_cookie_and_clears_cookies(client: AsyncClient, student_user: User) -> None:
    await _login(client)
    refresh = client.cookies.get(REFRESH_COOKIE)

    resp = await client.post("/api/v1/auth/logout", headers=CSRF)
    assert resp.status_code == 200
    cleared = resp.headers.get_list("set-cookie")
    assert any(c.startswith(f'{ACCESS_COOKIE}=""') or c.startswith(f"{ACCESS_COOKIE}=;") for c in cleared)
    assert any(c.startswith(f'{REFRESH_COOKIE}=""') or c.startswith(f"{REFRESH_COOKIE}=;") for c in cleared)

    assert (await client.get("/api/v1/auth/me")).status_code == 401
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401


def test_websocket_refuses_valid_jwt_in_url(student_user: User) -> None:
    """The `?token=` fallback is gone: only single-use tickets authenticate the WebSocket."""
    token = create_access_token(subject=student_user.id, role=student_user.role.value)
    with TestClient(app) as tc:
        with pytest.raises(WebSocketDisconnect) as closed:
            with tc.websocket_connect(f"/api/v1/ws/sessions/any-session?token={token}") as ws:
                ws.receive_json()
    assert closed.value.code == 4401

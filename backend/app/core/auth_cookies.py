"""httpOnly cookie session for the browser frontend.

The browser never sees a token: login and refresh set two httpOnly cookies, so script running in the
page (e.g. after an XSS bug) cannot read or exfiltrate them. Non-browser clients keep using
`Authorization: Bearer <token>`.

CSRF: cookies are sent automatically, so every state-changing request that relies on them must carry
the `X-VivaIQ-CSRF` header (checked where the cookie is read: `require_csrf_header`). A cross-origin page cannot add a custom header without a CORS preflight,
which only `CORS_ORIGINS` pass. SameSite=Lax is a second layer.
"""

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings

ACCESS_COOKIE = "vivaiq_access"
REFRESH_COOKIE = "vivaiq_refresh"
CSRF_HEADER = "X-VivaIQ-CSRF"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _refresh_path() -> str:
    # The refresh token is only ever sent to the auth routes (refresh, logout).
    return f"{settings.API_V1_STR}/auth"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "secure": bool(settings.AUTH_COOKIE_SECURE),
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "domain": settings.AUTH_COOKIE_DOMAIN,
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=settings.API_V1_STR,
        **common,  # type: ignore[arg-type]
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=_refresh_path(),
        **common,  # type: ignore[arg-type]
    )


def clear_auth_cookies(response: Response) -> None:
    for name, path in ((ACCESS_COOKIE, settings.API_V1_STR), (REFRESH_COOKIE, _refresh_path())):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.AUTH_COOKIE_DOMAIN,
            secure=bool(settings.AUTH_COOKIE_SECURE),
            httponly=True,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )


def require_csrf_header(request: Request) -> None:
    """Call wherever an auth cookie is about to be trusted.

    Only cookie-authenticated, state-changing requests are checked: a Bearer header or a token in the
    body cannot be supplied by a cross-site page, so those requests are not exposed to CSRF.
    """
    if request.method in SAFE_METHODS or request.headers.get(CSRF_HEADER):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Missing {CSRF_HEADER} header on a cookie-authenticated request",
    )

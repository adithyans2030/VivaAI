"""Security utilities: password hashing, JWT token management, WebSocket tickets, and rate limiting."""

from datetime import datetime, timedelta, timezone
import secrets
import time
from typing import Any, Dict, Optional, Set
import uuid

import bcrypt
import jwt

from app.core.config import settings

# Thread-safe in-memory store for revoked refresh token JTIs
_revoked_tokens: Set[str] = set()

# In-memory store for short-lived, single-use WebSocket tickets
# ticket -> {"session_id": str, "user_id": str, "role": str, "expires_at": float, "used": bool}
_ws_tickets: Dict[str, Dict[str, Any]] = {}

# In-memory sliding window rate limiter
# key -> list of request timestamps
_rate_limit_records: Dict[str, list[float]] = {}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plain password matches its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt password hash."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str, role: str) -> str:
    """Create a signed JWT refresh token with unique jti for rotation and revocation."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        if jti and jti in _revoked_tokens:
            raise ValueError("Token has been revoked")
        return payload
    except jwt.PyJWTError as exc:
        raise ValueError(f"Invalid or expired token: {str(exc)}") from exc


def revoke_token_jti(jti: str) -> None:
    """Revoke a token by its unique JTI."""
    _revoked_tokens.add(jti)


def is_token_jti_revoked(jti: str) -> bool:
    """Check if token JTI is in the revocation blacklist."""
    return jti in _revoked_tokens


# =========================================================================
# Single-Use Short-Lived WebSocket Tickets (WS-2.3)
# =========================================================================


def create_ws_ticket(session_id: str, user_id: str, role: str, expiry_seconds: int = 30) -> str:
    """Generate a single-use ticket valid for 30 seconds for WebSocket connection."""
    # Clean up expired tickets periodically
    now = time.time()
    expired = [k for k, v in _ws_tickets.items() if v["expires_at"] < now]
    for k in expired:
        _ws_tickets.pop(k, None)

    ticket = f"wst_{secrets.token_urlsafe(32)}"
    _ws_tickets[ticket] = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "expires_at": now + expiry_seconds,
        "used": False,
    }
    return ticket


def consume_ws_ticket(ticket: str, expected_session_id: str) -> Dict[str, Any]:
    """Validate and consume a WebSocket ticket (single-use)."""
    now = time.time()
    record = _ws_tickets.get(ticket)

    if not record:
        raise ValueError("Invalid or unknown WebSocket ticket")

    if record["used"]:
        raise ValueError("WebSocket ticket has already been used")

    if record["expires_at"] < now:
        _ws_tickets.pop(ticket, None)
        raise ValueError("WebSocket ticket has expired")

    if record["session_id"] != expected_session_id:
        raise ValueError("WebSocket ticket does not match the requested viva session")

    # Mark as used immediately to guarantee single-use
    record["used"] = True
    return record


# =========================================================================
# In-Memory Sliding Window Rate Limiting (WS-2.3)
# =========================================================================


def check_rate_limit(key: str, max_requests: int = 5, window_seconds: int = 60) -> bool:
    """Return True if request is allowed, False if rate limit is exceeded."""
    now = time.time()
    window_start = now - window_seconds

    if key not in _rate_limit_records:
        _rate_limit_records[key] = []

    # Retain only timestamps within sliding window
    _rate_limit_records[key] = [t for t in _rate_limit_records[key] if t > window_start]

    if len(_rate_limit_records[key]) >= max_requests:
        return False

    _rate_limit_records[key].append(now)
    return True

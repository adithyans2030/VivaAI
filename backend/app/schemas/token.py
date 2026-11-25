"""Token Pydantic Schemas."""

from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    # Omitted when the browser refreshes with its httpOnly cookie: the new tokens go back
    # only as cookies, so page script never sees them.
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: str
    type: str
    exp: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str

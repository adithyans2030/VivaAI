"""Token Pydantic Schemas."""

from typing import Optional
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: str
    type: str
    exp: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str

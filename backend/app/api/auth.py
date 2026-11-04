"""Authentication and User Management routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.token import RefreshTokenRequest, Token
from app.schemas.user import UserAdminCreate, UserRegister, UserResponse
from app.services import auth_state

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserRegister,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a new student account. Public self-registration is strictly restricted to STUDENT role."""
    client_ip = request.client.host if request.client else "unknown"
    if not await auth_state.allow_request(db, f"reg_{client_ip}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait before retrying.",
        )

    stmt = select(User).where(User.email == user_in.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists",
        )

    # Security: Always force role to STUDENT on public self-registration (WS-2.1)
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_privileged_user(
    user_in: UserAdminCreate,
    current_admin: Annotated[User, Depends(require_role([UserRole.ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Admin-only endpoint to create teacher and administrator accounts (WS-2.1)."""
    stmt = select(User).where(User.email == user_in.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists",
        )

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """OAuth2 compatible token login with rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login_{client_ip}_{form_data.username}"
    if not await auth_state.allow_request(db, rate_key, max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 1 minute before trying again.",
        )

    stmt = select(User).where(User.email == form_data.username)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id, role=user.role.value)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    body: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Exchange a valid refresh token for a fresh access token with token rotation (WS-2.3)."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        old_jti = payload.get("jti")
        user_id = payload.get("sub")
        if not old_jti:
            raise ValueError("Token has no id")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired refresh token: {str(exc)}",
        )

    # Rotation: each refresh token works once. A second use (replay or race) is refused.
    if not await auth_state.revoke_once(db, old_jti, float(payload["exp"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token: Token has been revoked",
        )

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists or is inactive",
        )

    new_access = create_access_token(subject=user.id, role=user.role.value)
    new_refresh = create_refresh_token(subject=user.id, role=user.role.value)

    return Token(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Optional[RefreshTokenRequest] = None,
) -> dict:
    """Revoke tokens upon logout (WS-2.3)."""
    if body and body.refresh_token:
        try:
            payload = decode_token(body.refresh_token)
            jti = payload.get("jti")
            if jti and payload.get("sub") == current_user.id:
                await auth_state.revoke_once(db, jti, float(payload["exp"]))
        except Exception:
            pass
    return {"message": "Successfully logged out and revoked session token"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Get the current authenticated user's profile."""
    return current_user


@router.get("/me/export-data")
async def export_user_data(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """GDPR-style student data export endpoint (WS-2.5)."""
    from sqlalchemy.orm import selectinload

    from app.models.session import VivaSession

    stmt = (
        select(VivaSession)
        .where(VivaSession.student_id == current_user.id)
        .options(selectinload(VivaSession.turns), selectinload(VivaSession.subject))
    )
    sessions = (await db.execute(stmt)).scalars().all()

    sessions_export = []
    for s in sessions:
        sessions_export.append(
            {
                "session_id": s.id,
                "subject_name": s.subject.name if s.subject else None,
                "status": s.status.value,
                "total_score": s.total_score,
                "authenticity_likelihood": s.overall_authenticity_likelihood.value
                if s.overall_authenticity_likelihood
                else None,
                "created_at": s.created_at.isoformat(),
                "turns": [
                    {
                        "turn_number": t.turn_number,
                        "topic": t.topic,
                        "question_text": t.question_text,
                        "transcript": t.transcript,
                        "score_0_10": t.score_0_10,
                        "feedback": t.feedback,
                    }
                    for t in s.turns
                ],
            }
        )

    return {
        "user_profile": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role.value,
            "created_at": current_user.created_at.isoformat(),
        },
        "viva_examinations": sessions_export,
    }


@router.delete("/me/delete-account-data")
async def delete_user_account_data(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Student data deletion endpoint: permanently purges audio, sessions, and account (WS-2.5)."""
    import shutil

    from app.models.session import VivaSession

    # Delete audio files
    stmt = select(VivaSession).where(VivaSession.student_id == current_user.id)
    sessions = (await db.execute(stmt)).scalars().all()
    for s in sessions:
        session_audio_dir = settings.AUDIO_STORAGE_PATH / s.id
        if session_audio_dir.exists():
            shutil.rmtree(session_audio_dir, ignore_errors=True)
        await db.delete(s)

    # Delete user account
    await db.delete(current_user)
    await db.commit()

    return {"message": "All user data, audio recordings, and examination history permanently purged"}

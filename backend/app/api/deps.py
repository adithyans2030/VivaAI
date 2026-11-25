"""FastAPI Route Dependencies."""

from typing import Annotated, Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookies import ACCESS_COOKIE, require_csrf_header
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.session import VivaSession
from app.models.subject import Subject
from app.models.user import User, UserRole

# auto_error=False: the browser authenticates with the httpOnly cookie instead of the header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    bearer_token: Annotated[Optional[str], Depends(oauth2_scheme)],
) -> User:
    """Authenticate with the Bearer header (API clients) or the access cookie (browser)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = bearer_token or request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise credentials_exception
    if not bearer_token:
        require_csrf_header(request)
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except Exception:
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )
    return user


def require_role(roles: List[UserRole]) -> Callable:
    """Dependency factory checking user role membership."""

    async def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {[r.value for r in roles]}",
            )
        return current_user

    return role_checker


async def ensure_session_access(db: AsyncSession, user: User, session: VivaSession) -> None:
    """Students may access only their own sessions; teachers only sessions in subjects they own.

    One rule for every session read or write (reports, overrides, exports, audio, tickets),
    so transcripts and recordings are never visible to unrelated teachers.
    """
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.STUDENT:
        if session.student_id == user.id:
            return
    elif user.role == UserRole.TEACHER:
        owner = (await db.execute(select(Subject.teacher_id).where(Subject.id == session.subject_id))).scalar()
        if owner == user.id:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this viva session")


def ensure_subject_owner(user: User, subject: Subject) -> None:
    """Only the subject's owning teacher (or an admin) may change its documents."""
    if user.role != UserRole.ADMIN and subject.teacher_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage subjects you own")

"""Pytest configuration and asynchronous fixtures."""

import os

# Set testing environment variables before any app modules are loaded
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEMO_MODE"] = "true"
os.environ["STT_PROVIDER"] = "mock"
os.environ["LLM_PROVIDER"] = "mock"

from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User, UserRole

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

test_async_session = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create all tables before each test and enforce mock providers for fast, deterministic CI."""
    from app.core.config import settings
    import app.services.llm as llm_module
    import app.services.stt as stt_module

    prev_env = settings.ENVIRONMENT
    prev_demo = settings.DEMO_MODE
    prev_llm = settings.LLM_PROVIDER
    prev_stt = settings.STT_PROVIDER

    settings.ENVIRONMENT = "testing"
    settings.DEMO_MODE = True
    settings.LLM_PROVIDER = "mock"
    settings.STT_PROVIDER = "mock"
    llm_module._llm_instance = None
    stt_module._stt_instance = None

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    settings.ENVIRONMENT = prev_env
    settings.DEMO_MODE = prev_demo
    settings.LLM_PROVIDER = prev_llm
    settings.STT_PROVIDER = prev_stt
    llm_module._llm_instance = None
    stt_module._stt_instance = None


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for test setup."""
    async with test_async_session() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client with DB dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    """Create a default teacher user."""
    teacher = User(
        email="teacher@vivaiq.edu",
        hashed_password=get_password_hash("teacher123"),
        full_name="Prof. Alan Turing",
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    await db_session.commit()
    await db_session.refresh(teacher)
    return teacher


@pytest.fixture
async def student_user(db_session: AsyncSession) -> User:
    """Create a default student user."""
    student = User(
        email="student@vivaiq.edu",
        hashed_password=get_password_hash("student123"),
        full_name="Ada Lovelace",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student

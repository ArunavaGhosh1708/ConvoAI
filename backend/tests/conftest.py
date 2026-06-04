import os
import time

# Set required env vars before any app module is imported so pydantic-settings
# doesn't fail on missing fields during the test collection phase.
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock

from app.database import Base, get_db
from app.main import app
from app.services.redis_client import get_redis

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://convoai:convoai@localhost:5432/convoai",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

# ---------------------------------------------------------------------------
# JWT helpers (reusable across test modules)
# ---------------------------------------------------------------------------

def make_jwt(role: str = "user", sub: str = "test-user") -> str:
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def admin_jwt() -> str:
    return make_jwt(role="admin", sub="test-admin")


def user_jwt() -> str:
    return make_jwt(role="user", sub="test-user")


# ---------------------------------------------------------------------------
# Integration-test fixtures (require live Postgres)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # No drop_all — the CI database is ephemeral (fresh container each run).
    # Dropping tables here races with pytest-asyncio's session event loop
    # teardown and causes asyncpg "another operation is in progress" errors
    # on whichever test happens to be last in the session.


@pytest_asyncio.fixture
async def db_session(setup_test_db):
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit-test fixture — no live DB or Redis
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_client():
    """HTTP test client with DB and Redis replaced by AsyncMocks — no live services."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()

    async def override_get_db():
        yield mock_db

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, mock_db, mock_redis

    app.dependency_overrides.clear()

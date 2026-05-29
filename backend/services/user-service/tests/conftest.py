"""
pytest fixtures for user-service tests.

Uses SQLite (aiosqlite) in-memory for DB and fakeredis for Redis — no
external services required to run the test suite.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock

from app.main import app
from app.database import Base, get_db
from app.redis_client import get_redis


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSessionFactory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test and drop after."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
def redis_mock():
    """In-memory Redis mock using AsyncMock."""
    store: dict = {}

    mock = AsyncMock()

    async def _set(key, value, ex=None):
        store[key] = value

    async def _get(key):
        return store.get(key)

    async def _delete(*keys):
        for k in keys:
            store.pop(k, None)

    async def _expire(key, seconds):
        pass  # no-op for tests

    mock.set.side_effect = _set
    mock.get.side_effect = _get
    mock.delete.side_effect = _delete
    mock.expire.side_effect = _expire
    return mock, store


@pytest_asyncio.fixture
async def client(redis_mock):
    """AsyncClient with DB and Redis overrides applied."""
    mock, store = redis_mock

    async def override_db():
        async with _TestSessionFactory() as session:
            yield session

    def override_redis():
        return mock

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, store

    app.dependency_overrides.clear()

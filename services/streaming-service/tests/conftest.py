"""
pytest fixtures for streaming-service tests.

Uses SQLite in-memory for DB and AsyncMock for Redis — no external services.
Temporary directory is used as media root for HLS file serving.
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock

from app.main import app
from app.database import Base, get_db
from app.redis_client import get_redis

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSessionFactory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
def redis_mock():
    store: dict = {}
    mock = AsyncMock()

    async def _set(key, value, ex=None): store[key] = value
    async def _get(key): return store.get(key)
    async def _delete(*keys):
        for k in keys: store.pop(k, None)

    mock.set.side_effect = _set
    mock.get.side_effect = _get
    mock.delete.side_effect = _delete
    return mock, store


@pytest_asyncio.fixture
async def client(redis_mock, tmp_path):
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
        yield ac, store, tmp_path

    app.dependency_overrides.clear()

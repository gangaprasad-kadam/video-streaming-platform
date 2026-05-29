"""
pytest fixtures for streaming-service tests.

Uses AsyncMock for Redis — no database or external services needed.
streaming-service now gets video metadata via HTTP from video-service (mocked in tests).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock

from app.main import app
from app.redis_client import get_redis


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

    def override_redis():
        return mock

    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, store, tmp_path

    app.dependency_overrides.clear()

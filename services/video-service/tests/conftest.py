"""
pytest fixtures for video-service tests.

- SQLite in-memory for DB (no Postgres needed)
- AsyncMock for Redis
- AsyncMock for Kafka publisher
- Temp directory for media storage
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch
import tempfile, os

from app.main import app
from app.database import Base, get_db
from app.redis_client import get_redis
import app.kafka_producer as kp

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)


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
    async def _expire(key, secs): pass

    mock.set.side_effect = _set
    mock.get.side_effect = _get
    mock.delete.side_effect = _delete
    mock.expire.side_effect = _expire
    return mock, store


@pytest_asyncio.fixture
def kafka_mock():
    """Patch kafka_producer.publish to capture published events."""
    published = []

    async def fake_publish(topic, key, value):
        published.append({"topic": topic, "key": key, "value": value})

    with patch.object(kp, "publish", side_effect=fake_publish):
        yield published


@pytest_asyncio.fixture
async def client(redis_mock, kafka_mock, tmp_path):
    mock, store = redis_mock

    # Seed a session so we can authenticate
    store["session:test-session-id"] = "11111111-1111-1111-1111-111111111111"

    async def override_db():
        async with _TestSession() as session:
            yield session

    def override_redis():
        return mock

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    # Point media root to a temp dir so file writes don't fail
    with patch("app.config.settings.MEDIA_ROOT", str(tmp_path)):
        with patch("app.videos.service.settings.MEDIA_ROOT", str(tmp_path)):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                yield ac, store, kafka_mock

    app.dependency_overrides.clear()

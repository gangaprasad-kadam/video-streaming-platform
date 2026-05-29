import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.kafka_producer import get_producer
from app.redis_client import get_redis


@pytest.fixture
def mock_producer():
    producer = AsyncMock()
    producer.send_and_wait = AsyncMock()
    return producer


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    return redis


@pytest.fixture
def client(mock_producer, mock_redis):
    app.dependency_overrides[get_producer] = lambda: mock_producer
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_ingest_play_event(async_client, mock_producer):
    response = await async_client.post("/events/interaction", json={
        "userId": "user-1",
        "videoId": "vid-abc",
        "action": "PLAY",
        "videoTs": 0.0,
        "creatorId": "creator-1",
        "sessionId": "sess-1",
    })
    assert response.status_code == 202
    data = response.json()
    assert data["accepted"] is True
    assert data["action"] == "PLAY"
    assert data["videoId"] == "vid-abc"
    mock_producer.send_and_wait.assert_called_once()


async def test_ingest_invalid_action(async_client):
    response = await async_client.post("/events/interaction", json={
        "userId": "user-1",
        "videoId": "vid-abc",
        "action": "INVALID_ACTION",
    })
    assert response.status_code == 422


async def test_rate_limit_exceeded(async_client, mock_redis, mock_producer):
    mock_redis.incr = AsyncMock(return_value=61)  # over limit
    response = await async_client.post("/events/interaction", json={
        "userId": "user-1",
        "videoId": "vid-abc",
        "action": "PAUSE",
    })
    assert response.status_code == 429
    assert response.json()["error"] == "RATE_LIMIT_EXCEEDED"
    mock_producer.send_and_wait.assert_not_called()


async def test_health(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.redis_client import get_redis
from app.mongo_client import get_db
from app.heatmap.utils.schemas import InteractionEvent
from app.heatmap.utils import service as heatmap_service
from app.heatmap.utils.cache import record_event, _bucket


# ── unit: bucket mapping ────────────────────────────────────────────────────

def test_bucket_exact():
    assert _bucket(0.0) == 0
    assert _bucket(5.0) == 5
    assert _bucket(10.0) == 10

def test_bucket_rounds_down():
    assert _bucket(7.9) == 5
    assert _bucket(142.5) == 140
    assert _bucket(144.9) == 140
    assert _bucket(145.0) == 145


# ── unit: record_event writes correct Redis keys ────────────────────────────

async def test_record_event_increments_correct_bucket():
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=pipe)

    event = InteractionEvent(userId="u1", videoId="vid-1", action="REWIND", videoTs=142.5)
    bucket = await record_event(redis, event)

    assert bucket == 140
    pipe.incrby.assert_any_call("heatmap:vid-1:total:140", 3)  # REWIND weight=3
    pipe.incrby.assert_any_call("heatmap:vid-1:live:140", 3)


async def test_record_event_skip_negative_weight():
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=pipe)

    event = InteractionEvent(userId="u1", videoId="vid-1", action="SKIP", videoTs=30.0)
    bucket = await record_event(redis, event)

    assert bucket == 30
    pipe.incrby.assert_any_call("heatmap:vid-1:total:30", -1)  # SKIP weight=-1


# ── unit: handle_interaction calls repo upsert ──────────────────────────────

async def test_handle_interaction_unknown_action_skipped():
    db = AsyncMock()
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=pipe)

    event = InteractionEvent(userId="u1", videoId="vid-1", action="UNKNOWN", videoTs=10.0)
    with patch("app.heatmap.dao.repository.upsert_bucket") as mock_upsert:
        await heatmap_service.handle_interaction(db, redis, event)
        mock_upsert.assert_not_called()


async def test_handle_interaction_upserts_mongo():
    db = AsyncMock()
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=pipe)

    event = InteractionEvent(userId="u1", videoId="vid-1", action="PAUSE", videoTs=60.0)
    with patch("app.heatmap.dao.repository.upsert_bucket", new_callable=AsyncMock) as mock_upsert:
        await heatmap_service.handle_interaction(db, redis, event)
        mock_upsert.assert_called_once_with(db, "vid-1", 60, 1)  # PAUSE weight=1


# ── integration: health endpoint ────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def client_overrides(mock_redis, mock_db):
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()


async def test_health(client_overrides):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

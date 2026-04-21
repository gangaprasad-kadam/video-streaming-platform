import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.redis_client import get_redis
from app.mongo_client import get_db
from app.heatmap.utils.schemas import make_label


# ── unit: label formatting ───────────────────────────────────────────────────

def test_make_label_zero():
    assert make_label(0, 5) == "0:00–0:05"

def test_make_label_minute_boundary():
    assert make_label(60, 5) == "1:00–1:05"

def test_make_label_mid_video():
    assert make_label(140, 5) == "2:20–2:25"

def test_make_label_large():
    assert make_label(3600, 5) == "60:00–60:05"


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def client_overrides(mock_redis, mock_db):
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def ac(client_overrides):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ── GET /heatmap/{video_id} ───────────────────────────────────────────────────

async def test_get_heatmap_returns_data(ac, mock_db):
    mock_db.heatmap_buckets = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=[
        {"bucket": 0, "score": 2},
        {"bucket": 140, "score": 47},
    ])
    mock_db.heatmap_buckets.find = MagicMock(return_value=mock_cursor)

    response = await ac.get("/heatmap/vid-abc")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["video_id"] == "vid-abc"
    assert data["total_buckets"] == 2
    assert data["buckets"][1]["bucket"] == 140
    assert data["buckets"][1]["score"] == 47
    assert data["buckets"][1]["label"] == "2:20–2:25"


async def test_get_heatmap_not_found(ac, mock_db):
    mock_db.heatmap_buckets = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_db.heatmap_buckets.find = MagicMock(return_value=mock_cursor)

    response = await ac.get("/heatmap/no-such-video")
    assert response.status_code == 404


# ── GET /heatmap/{video_id}/live ──────────────────────────────────────────────

async def test_get_live_heatmap_empty(ac, mock_redis):
    mock_redis.keys = AsyncMock(return_value=[])
    response = await ac.get("/heatmap/vid-abc/live")
    assert response.status_code == 200
    assert response.json()["data"]["total_buckets"] == 0


async def test_get_live_heatmap_with_data(ac, mock_redis):
    mock_redis.keys = AsyncMock(return_value=["heatmap:vid-abc:live:140"])
    mock_redis.get = AsyncMock(return_value="12")
    response = await ac.get("/heatmap/vid-abc/live")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_buckets"] == 1
    assert data["buckets"][0]["bucket"] == 140
    assert data["buckets"][0]["score"] == 12


# ── GET /heatmap/{video_id}/highlights ────────────────────────────────────────

async def test_get_highlights(ac, mock_db):
    mock_db.heatmap_buckets = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=[
        {"bucket": 140, "score": 47},
        {"bucket": 60, "score": 20},
    ])
    mock_db.heatmap_buckets.find = MagicMock(return_value=mock_cursor)

    response = await ac.get("/heatmap/vid-abc/highlights?limit=2")
    assert response.status_code == 200
    highlights = response.json()["data"]["highlights"]
    assert len(highlights) == 2
    assert highlights[0]["score"] == 47


# ── health ────────────────────────────────────────────────────────────────────

async def test_health(ac):
    response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

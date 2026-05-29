import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "trending-service"}


@pytest.mark.asyncio
async def test_trending_empty(client, mock_redis):
    """Returns empty list when Redis sorted set is empty."""
    mock_redis.zrevrange.return_value = []

    resp = await client.get("/trending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["videos"] == []
    assert body["data"]["total"] == 0


@pytest.mark.asyncio
async def test_trending_with_scores(client, mock_redis):
    """Returns ranked videos when Redis has entries and video-service returns metadata."""
    import uuid

    video_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())

    mock_redis.zrevrange.return_value = [(video_id, 5.0)]

    # Mock the HTTP call to video-service
    with patch(
        "app.trending.utils.video_client.get_videos_by_ids",
        new=AsyncMock(return_value=[{
            "id": video_id,
            "title": "Test Video",
            "creator_id": creator_id,
            "thumbnail_path": None,
            "duration": 60.0,
            "status": "ready",
        }]),
    ):
        resp = await client.get("/trending?limit=10")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]["videos"]) == 1
    item = body["data"]["videos"][0]
    assert item["video_id"] == video_id
    assert item["title"] == "Test Video"
    assert item["score"] == 5.0
    assert item["rank"] == 1


@pytest.mark.asyncio
async def test_trending_skips_non_ready_videos(client, mock_redis):
    """Videos not returned by video-service (deleted/not ready) are silently skipped."""
    import uuid

    ghost_id = str(uuid.uuid4())
    mock_redis.zrevrange.return_value = [(ghost_id, 99.0)]

    # video-service returns empty list (video not ready / deleted)
    with patch(
        "app.trending.utils.video_client.get_videos_by_ids",
        new=AsyncMock(return_value=[]),
    ):
        resp = await client.get("/trending")

    assert resp.status_code == 200
    assert resp.json()["data"]["videos"] == []


@pytest.mark.asyncio
async def test_trending_limit_query_param(client, mock_redis):
    """Accepts and forwards limit query parameter."""
    mock_redis.zrevrange.return_value = []

    with patch(
        "app.trending.utils.video_client.get_videos_by_ids",
        new=AsyncMock(return_value=[]),
    ):
        resp = await client.get("/trending?limit=5")

    assert resp.status_code == 200
    mock_redis.zrevrange.assert_called_once_with("trending:scores", 0, 4, withscores=True)


@pytest.mark.asyncio
async def test_recommendations_empty_history(client, mock_redis):
    """Returns only trending slice when user has no watch history."""
    import uuid

    user_id = str(uuid.uuid4())
    mock_redis.zrevrange.return_value = []

    with patch(
        "app.trending.utils.video_client.get_videos_by_ids",
        new=AsyncMock(return_value=[]),
    ):
        resp = await client.get(f"/trending/recommendations/{user_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["user_id"] == user_id
    assert body["data"]["videos"] == []


@pytest.mark.asyncio
async def test_recommendations_blends_trending_and_creator(client, mock_redis, db_session):
    """Blends 60% trending + 40% creator-based; already-watched videos excluded."""
    import uuid
    from app.models import WatchHistory

    user_id = uuid.uuid4()
    creator_id = uuid.uuid4()
    watched_video_id = uuid.uuid4()
    trending_video_id = uuid.uuid4()
    creator_video_id = uuid.uuid4()

    # User watched one video
    db_session.add(
        WatchHistory(
            user_id=user_id,
            video_id=watched_video_id,
            creator_id=creator_id,
        )
    )
    await db_session.commit()

    # Redis returns trending video (unwatched)
    mock_redis.zrevrange.return_value = [(str(trending_video_id), 8.0)]

    trending_data = [{
        "id": str(trending_video_id),
        "title": "Trending Video",
        "creator_id": str(uuid.uuid4()),
        "thumbnail_path": None,
        "duration": None,
        "status": "ready",
    }]
    creator_data = [{
        "id": str(creator_video_id),
        "title": "Creator Video",
        "creator_id": str(creator_id),
        "thumbnail_path": None,
        "duration": None,
        "status": "ready",
    }]

    with (
        patch("app.trending.utils.video_client.get_videos_by_ids", new=AsyncMock(return_value=trending_data)),
        patch("app.trending.utils.video_client.get_videos_by_creators", new=AsyncMock(return_value=creator_data)),
    ):
        resp = await client.get(f"/trending/recommendations/{user_id}?limit=10")

    assert resp.status_code == 200
    body = resp.json()

    video_ids = {v["video_id"] for v in body["data"]["videos"]}
    reasons = {v["video_id"]: v["reason"] for v in body["data"]["videos"]}

    assert str(trending_video_id) in video_ids
    assert reasons[str(trending_video_id)] == "trending"

    assert str(creator_video_id) in video_ids
    assert reasons[str(creator_video_id)] == "creator"

    assert str(watched_video_id) not in video_ids

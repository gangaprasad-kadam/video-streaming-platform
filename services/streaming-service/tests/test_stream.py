"""
Tests for streaming-service endpoints.
streaming-service no longer has a DB — video metadata comes from video-service over HTTP.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health(client):
    ac, _, _ = client
    resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "streaming-service"


@pytest.mark.asyncio
async def test_get_manifest_success(client):
    """Serves manifest from disk when video-service says the video is ready."""
    ac, store, tmp_path = client

    video_id = str(uuid.uuid4())
    hls_dir = tmp_path / "hls" / video_id
    hls_dir.mkdir(parents=True)
    manifest_file = hls_dir / "index.m3u8"
    manifest_file.write_text("#EXTM3U\n#EXT-X-VERSION:3\n")

    with patch(
        "app.stream.utils.video_client.get_stream_info",
        new=AsyncMock(return_value={
            "id": video_id,
            "status": "ready",
            "hls_path": str(manifest_file),
        }),
    ):
        resp = await ac.get(f"/stream/{video_id}/index.m3u8")

    assert resp.status_code == 200
    assert "#EXTM3U" in resp.text
    assert resp.headers["content-type"].startswith("application/vnd.apple.mpegurl")


@pytest.mark.asyncio
async def test_get_manifest_cached(client):
    """Returns manifest from Redis cache without calling video-service."""
    ac, store, tmp_path = client

    video_id = str(uuid.uuid4())
    store[f"stream:manifest:{video_id}"] = "#EXTM3U\n#EXT-X-VERSION:3\n"

    with patch(
        "app.stream.utils.video_client.get_stream_info",
        new=AsyncMock(side_effect=AssertionError("should not be called")),
    ):
        resp = await ac.get(f"/stream/{video_id}/index.m3u8")

    assert resp.status_code == 200
    assert "#EXTM3U" in resp.text


@pytest.mark.asyncio
async def test_get_manifest_video_not_ready(client):
    """Returns 425 when video-service says video is not ready."""
    ac, _, _ = client

    video_id = str(uuid.uuid4())

    with patch(
        "app.stream.utils.video_client.get_stream_info",
        new=AsyncMock(return_value=None),
    ):
        resp = await ac.get(f"/stream/{video_id}/index.m3u8")

    assert resp.status_code == 425


@pytest.mark.asyncio
async def test_get_manifest_no_hls_path(client):
    """Returns 404 when video is ready but has no hls_path set."""
    ac, _, _ = client

    video_id = str(uuid.uuid4())

    with patch(
        "app.stream.utils.video_client.get_stream_info",
        new=AsyncMock(return_value={
            "id": video_id,
            "status": "ready",
            "hls_path": None,
        }),
    ):
        resp = await ac.get(f"/stream/{video_id}/index.m3u8")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalidate_cache(client):
    """Cache invalidation removes both manifest and hls_path entries from Redis."""
    ac, store, _ = client

    video_id = str(uuid.uuid4())
    store[f"stream:manifest:{video_id}"] = "#EXTM3U"
    store[f"stream:hls:{video_id}"] = "/media/hls/some/index.m3u8"

    resp = await ac.delete(f"/stream/internal/{video_id}/cache")
    assert resp.status_code == 200
    assert f"stream:manifest:{video_id}" not in store
    assert f"stream:hls:{video_id}" not in store

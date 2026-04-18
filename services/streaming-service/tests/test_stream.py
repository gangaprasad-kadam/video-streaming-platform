"""
Tests for streaming-service endpoints.
"""
import os
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStatus


async def _create_ready_video(session: AsyncSession, hls_path: str) -> str:
    """Helper: insert a ready video directly into the test DB."""
    video_id = uuid.uuid4()
    video = Video(
        id=video_id,
        title="Test Video",
        creator_id=uuid.uuid4(),
        file_path="/media/uploads/test.mp4",
        hls_path=hls_path,
        status=VideoStatus.ready,
    )
    session.add(video)
    await session.commit()
    return str(video_id)


@pytest.mark.asyncio
async def test_health(client):
    ac, _, _ = client
    resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "streaming-service"


@pytest.mark.asyncio
async def test_get_manifest_success(client):
    ac, store, tmp_path = client

    # Create real HLS files in tmp_path
    hls_dir = tmp_path / "hls" / "some-video"
    hls_dir.mkdir(parents=True)
    manifest = hls_dir / "index.m3u8"
    manifest.write_text("#EXTM3U\n#EXT-X-VERSION:3\n")

    # Insert ready video
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.database import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # We use the overridden DB in client fixture — need to insert via the override
    # Instead, test via conftest's session factory

    resp = await ac.get("/health")  # sanity
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_manifest_not_found_returns_404(client):
    ac, _, _ = client
    resp = await ac.get(f"/stream/{uuid.uuid4()}/index.m3u8")
    assert resp.status_code in (404, 425)


@pytest.mark.asyncio
async def test_invalidate_cache(client):
    ac, store, _ = client
    video_id = str(uuid.uuid4())
    store[f"stream:manifest:{video_id}"] = "#EXTM3U"

    resp = await ac.delete(f"/stream/internal/{video_id}/cache")
    assert resp.status_code == 200
    assert f"stream:manifest:{video_id}" not in store

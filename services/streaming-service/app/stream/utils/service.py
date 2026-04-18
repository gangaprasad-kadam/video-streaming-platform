import os

import aiofiles
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import StreamNotFoundError, VideoNotReadyError
from app.stream.dao import repository as repo
from app.stream.utils.cache import cache_manifest, get_cached_manifest


async def get_manifest(db: AsyncSession, redis: Redis, video_id: str) -> str:
    """Return the HLS manifest content for a ready video.

    Checks Redis first. On a cache miss, reads the manifest from disk and
    stores it in Redis with a 5-minute TTL.

    Args:
        db: Active async database session.
        redis: Active Redis client.
        video_id: UUID string of the video.

    Returns:
        The raw text content of the ``.m3u8`` manifest file.

    Raises:
        VideoNotReadyError: If the video is not in the ``ready`` state.
        StreamNotFoundError: If the manifest file is missing from disk.
    """
    cached = await get_cached_manifest(redis, video_id)
    if cached:
        return cached

    video = await repo.get_ready_video(db, video_id)
    if not video:
        raise VideoNotReadyError(video_id)
    if not video.hls_path:
        raise StreamNotFoundError(video_id)

    manifest_path = video.hls_path
    if not os.path.isfile(manifest_path):
        raise StreamNotFoundError(manifest_path)

    async with aiofiles.open(manifest_path, "r") as f:
        content = await f.read()

    await cache_manifest(redis, video_id, content)
    return content


async def get_segment_path(db: AsyncSession, video_id: str, segment: str) -> str:
    """Resolve and validate the absolute path to a requested HLS segment.

    Args:
        db: Active async database session.
        video_id: UUID string of the video.
        segment: Filename of the segment (e.g. ``seg0.ts``).

    Returns:
        Absolute filesystem path to the segment file.

    Raises:
        VideoNotReadyError: If the video is not in the ``ready`` state.
        StreamNotFoundError: If the segment file does not exist on disk.
    """
    video = await repo.get_ready_video(db, video_id)
    if not video:
        raise VideoNotReadyError(video_id)
    if not video.hls_path:
        raise StreamNotFoundError(video_id)

    # hls_path = /media/hls/{videoId}/index.m3u8 → base dir = /media/hls/{videoId}/
    hls_dir = os.path.dirname(video.hls_path)
    segment_path = os.path.join(hls_dir, segment)

    if not os.path.isfile(segment_path):
        raise StreamNotFoundError(segment_path)

    return segment_path

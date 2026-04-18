import os

import aiofiles
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import StreamNotFoundError, VideoNotReadyError
from app.stream.dao import repository as repo
from app.stream.utils.cache import cache_manifest, get_cached_manifest


async def get_manifest(db: AsyncSession, redis: Redis, video_id: str) -> str:
    """Return HLS manifest content. Uses Redis cache (5min TTL)."""
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
    """Validate video is ready and return the absolute path to the segment file."""
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

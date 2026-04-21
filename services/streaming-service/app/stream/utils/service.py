import os

import aiofiles
from redis.asyncio import Redis

from app.exceptions import StreamNotFoundError, VideoNotReadyError
from app.stream.utils import video_client
from app.stream.utils.cache import (
    cache_hls_path,
    cache_manifest,
    get_cached_hls_path,
    get_cached_manifest,
)


async def _resolve_hls_path(redis: Redis, video_id: str) -> str:
    """Return the HLS playlist path for a ready video.

    Checks Redis first; on a miss, calls video-service over HTTP and caches the result.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.

    Returns:
        Filesystem path to the HLS playlist file.

    Raises:
        VideoNotReadyError: If video-service reports the video is not ready.
        StreamNotFoundError: If the video is ready but has no hls_path.
    """
    cached = await get_cached_hls_path(redis, video_id)
    if cached:
        return cached

    info = await video_client.get_stream_info(video_id)
    if not info:
        raise VideoNotReadyError(video_id)

    hls_path = info.get("hls_path")
    if not hls_path:
        raise StreamNotFoundError(video_id)

    await cache_hls_path(redis, video_id, hls_path)
    return hls_path


async def get_manifest(redis: Redis, video_id: str) -> str:
    """Return the HLS manifest content for a ready video.

    Checks Redis manifest cache first. On a miss, resolves the HLS path via
    video-service (with its own Redis cache), reads the file, and stores the
    manifest content in Redis with a 5-minute TTL.

    Args:
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

    hls_path = await _resolve_hls_path(redis, video_id)

    if not os.path.isfile(hls_path):
        raise StreamNotFoundError(hls_path)

    async with aiofiles.open(hls_path, "r") as f:
        content = await f.read()

    await cache_manifest(redis, video_id, content)
    return content


async def get_segment_path(redis: Redis, video_id: str, segment: str) -> str:
    """Resolve and validate the absolute path to a requested HLS segment.

    Uses Redis-cached HLS path to avoid an HTTP call per segment request.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.
        segment: Filename of the segment (e.g. ``seg0.ts``).

    Returns:
        Absolute filesystem path to the segment file.

    Raises:
        VideoNotReadyError: If the video is not in the ``ready`` state.
        StreamNotFoundError: If the segment file does not exist on disk.
    """
    hls_path = await _resolve_hls_path(redis, video_id)

    # hls_path = /media/hls/{videoId}/index.m3u8 → base dir = /media/hls/{videoId}/
    hls_dir = os.path.dirname(hls_path)
    segment_path = os.path.join(hls_dir, segment)

    if not os.path.isfile(segment_path):
        raise StreamNotFoundError(segment_path)

    return segment_path

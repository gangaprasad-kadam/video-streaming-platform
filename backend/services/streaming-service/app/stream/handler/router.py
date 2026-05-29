import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, PlainTextResponse
from redis.asyncio import Redis

from app.redis_client import get_redis
from app.stream.utils import service as stream_service
from app.stream.utils.cache import invalidate_manifest_cache

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/{video_id}/index.m3u8", response_class=PlainTextResponse)
async def get_manifest(
    video_id: str,
    redis: Redis = Depends(get_redis),
):
    """Serve the HLS manifest (.m3u8) for a ready video.

    Checks Redis first (5-minute TTL) before calling video-service and reading
    the file from disk.  Returns 425 if the video is not yet ready.

    Args:
        video_id: UUID string of the target video.
        redis: Injected Redis client.

    Returns:
        PlainTextResponse with content type ``application/vnd.apple.mpegurl``.
    """
    content = await stream_service.get_manifest(redis, video_id)
    return PlainTextResponse(
        content=content,
        media_type="application/vnd.apple.mpegurl",
    )


@router.get("/{video_id}/{segment}")
async def get_segment(
    video_id: str,
    segment: str,
    redis: Redis = Depends(get_redis),
):
    """Serve an individual HLS segment (.ts) file.

    Supports HTTP range requests so clients can seek within a stream.
    Returns 425 if the video is not ready, or 404 if the segment is missing.

    Args:
        video_id: UUID string of the target video.
        segment: Filename of the requested segment (e.g. ``seg0.ts``).
        redis: Injected Redis client (used to resolve HLS path from cache).

    Returns:
        FileResponse with content type ``video/MP2T`` and ``Accept-Ranges: bytes`` header.
    """
    segment_path = await stream_service.get_segment_path(redis, video_id, segment)
    return FileResponse(
        path=segment_path,
        media_type="video/MP2T",
        headers={"Accept-Ranges": "bytes"},
    )


@router.delete("/internal/{video_id}/cache")
async def invalidate_cache(video_id: str, redis: Redis = Depends(get_redis)):
    """Invalidate the cached HLS manifest and HLS path for a video.

    Internal endpoint intended for use after re-encoding. Removes both Redis
    entries so the next manifest request re-reads from disk.

    Args:
        video_id: UUID string of the video whose cache should be cleared.
        redis: Injected Redis client.

    Returns:
        dict with a confirmation message.
    """
    await invalidate_manifest_cache(redis, video_id)
    return {"message": f"Cache invalidated for video {video_id}"}

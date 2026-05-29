from redis.asyncio import Redis

from app.config import settings

_KEY_PREFIX = "stream:manifest:"
_HLS_KEY_PREFIX = "stream:hls:"


async def get_cached_manifest(redis: Redis, video_id: str) -> str | None:
    """Fetch a cached HLS manifest from Redis.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.

    Returns:
        Manifest text if cached, or ``None`` on a cache miss.
    """
    return await redis.get(f"{_KEY_PREFIX}{video_id}")


async def cache_manifest(redis: Redis, video_id: str, content: str) -> None:
    """Store a manifest in Redis with the configured TTL.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.
        content: Raw manifest text to cache.
    """
    await redis.set(f"{_KEY_PREFIX}{video_id}", content, ex=settings.MANIFEST_CACHE_TTL)


async def get_cached_hls_path(redis: Redis, video_id: str) -> str | None:
    """Fetch a cached HLS directory path from Redis.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.

    Returns:
        HLS path string if cached, or ``None`` on a cache miss.
    """
    value = await redis.get(f"{_HLS_KEY_PREFIX}{video_id}")
    if isinstance(value, bytes):
        return value.decode()
    return value


async def cache_hls_path(redis: Redis, video_id: str, hls_path: str) -> None:
    """Store a video's HLS path in Redis with the configured TTL.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.
        hls_path: Filesystem path to the HLS playlist file.
    """
    await redis.set(f"{_HLS_KEY_PREFIX}{video_id}", hls_path, ex=settings.MANIFEST_CACHE_TTL)


async def invalidate_manifest_cache(redis: Redis, video_id: str) -> None:
    """Remove cached manifest and HLS path for a video from Redis.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video whose cache entries should be deleted.
    """
    await redis.delete(f"{_KEY_PREFIX}{video_id}", f"{_HLS_KEY_PREFIX}{video_id}")

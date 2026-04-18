from redis.asyncio import Redis

from app.config import settings

_KEY_PREFIX = "stream:manifest:"


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


async def invalidate_manifest_cache(redis: Redis, video_id: str) -> None:
    """Remove a cached manifest from Redis.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video whose cache entry should be deleted.
    """
    await redis.delete(f"{_KEY_PREFIX}{video_id}")

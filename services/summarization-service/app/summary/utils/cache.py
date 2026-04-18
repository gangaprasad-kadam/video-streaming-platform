import json

from redis.asyncio import Redis

from app.config import settings

_KEY_PREFIX = "summary:"


async def get_cached_summary(redis: Redis, video_id: str) -> dict | None:
    """Fetch a cached summary from Redis.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.

    Returns:
        Deserialized summary dict if cached, or ``None`` on a cache miss.
    """
    raw = await redis.get(f"{_KEY_PREFIX}{video_id}")
    return json.loads(raw) if raw else None


async def cache_summary(redis: Redis, video_id: str, data: dict) -> None:
    """Store a summary in Redis with the configured TTL.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.
        data: Summary payload dict to serialize and cache.
    """
    await redis.set(f"{_KEY_PREFIX}{video_id}", json.dumps(data), ex=settings.SUMMARY_CACHE_TTL)


async def invalidate_summary_cache(redis: Redis, video_id: str) -> None:
    """Remove a cached summary from Redis.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video whose cache entry should be deleted.
    """
    await redis.delete(f"{_KEY_PREFIX}{video_id}")

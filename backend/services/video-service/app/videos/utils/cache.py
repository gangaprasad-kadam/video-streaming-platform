import json

from redis.asyncio import Redis

_VIDEO_TTL = 300  # 5 minutes


async def cache_video_meta(redis: Redis, video_id: str, data: dict) -> None:
    """Store serialised video metadata in Redis with a 5-minute TTL.

    Args:
        redis: Async Redis client.
        video_id: UUID string used as part of the cache key.
        data: Dictionary of video fields to cache.
    """
    await redis.set(f"video:{video_id}", json.dumps(data), ex=_VIDEO_TTL)


async def get_cached_video(redis: Redis, video_id: str) -> dict | None:
    """Fetch cached video metadata from Redis.

    Args:
        redis: Async Redis client.
        video_id: UUID string of the video.

    Returns:
        Deserialised metadata dictionary, or ``None`` on a cache miss.
    """
    raw = await redis.get(f"video:{video_id}")
    return json.loads(raw) if raw else None


async def invalidate_video_cache(redis: Redis, video_id: str) -> None:
    """Delete a video's cached metadata from Redis.

    Args:
        redis: Async Redis client.
        video_id: UUID string of the video whose cache entry to remove.
    """
    await redis.delete(f"video:{video_id}")

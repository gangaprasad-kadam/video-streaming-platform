from redis.asyncio import Redis

from app.config import settings

_KEY_PREFIX = "stream:manifest:"


async def get_cached_manifest(redis: Redis, video_id: str) -> str | None:
    """Return cached manifest content, or None if not cached."""
    return await redis.get(f"{_KEY_PREFIX}{video_id}")


async def cache_manifest(redis: Redis, video_id: str, content: str) -> None:
    """Cache manifest content with configured TTL."""
    await redis.set(f"{_KEY_PREFIX}{video_id}", content, ex=settings.MANIFEST_CACHE_TTL)


async def invalidate_manifest_cache(redis: Redis, video_id: str) -> None:
    """Delete cached manifest (call after re-encoding)."""
    await redis.delete(f"{_KEY_PREFIX}{video_id}")

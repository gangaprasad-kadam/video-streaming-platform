import json

from redis.asyncio import Redis

from app.config import settings

_KEY_PREFIX = "summary:"


async def get_cached_summary(redis: Redis, video_id: str) -> dict | None:
    raw = await redis.get(f"{_KEY_PREFIX}{video_id}")
    return json.loads(raw) if raw else None


async def cache_summary(redis: Redis, video_id: str, data: dict) -> None:
    await redis.set(f"{_KEY_PREFIX}{video_id}", json.dumps(data), ex=settings.SUMMARY_CACHE_TTL)


async def invalidate_summary_cache(redis: Redis, video_id: str) -> None:
    await redis.delete(f"{_KEY_PREFIX}{video_id}")

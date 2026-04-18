import json

from redis.asyncio import Redis

_VIDEO_TTL = 300  # 5 minutes


async def cache_video_meta(redis: Redis, video_id: str, data: dict) -> None:
    await redis.set(f"video:{video_id}", json.dumps(data), ex=_VIDEO_TTL)


async def get_cached_video(redis: Redis, video_id: str) -> dict | None:
    raw = await redis.get(f"video:{video_id}")
    return json.loads(raw) if raw else None


async def invalidate_video_cache(redis: Redis, video_id: str) -> None:
    await redis.delete(f"video:{video_id}")

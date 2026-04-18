from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def connect_redis() -> None:
    global _redis
    _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    if _redis:
        await _redis.aclose()


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised — call connect_redis() first")
    return _redis

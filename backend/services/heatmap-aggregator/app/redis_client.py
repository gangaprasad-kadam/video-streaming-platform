from redis.asyncio import Redis

_redis: Redis | None = None


async def connect_redis() -> None:
    global _redis
    from app.config import settings
    _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised")
    return _redis

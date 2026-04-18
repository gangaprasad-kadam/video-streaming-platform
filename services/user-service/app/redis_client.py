from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def connect_redis() -> None:
    """Initialise the global Redis connection from settings."""
    global _redis
    _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    """Close the global Redis connection gracefully."""
    if _redis:
        await _redis.aclose()


def get_redis() -> Redis:
    """Return the active Redis client.

    Returns:
        The global Redis instance.

    Raises:
        RuntimeError: If ``connect_redis()`` has not been called yet.
    """
    if _redis is None:
        raise RuntimeError("Redis not initialised — call connect_redis() first")
    return _redis

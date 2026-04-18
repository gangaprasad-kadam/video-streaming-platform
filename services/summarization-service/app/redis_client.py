from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def connect_redis() -> None:
    """Initialise the global Redis connection from the configured URL."""
    global _redis
    _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    """Close the Redis connection if it is open."""
    if _redis:
        await _redis.aclose()


def get_redis() -> Redis:
    """Return the active Redis client.

    Returns:
        Redis: The active Redis client instance.

    Raises:
        RuntimeError: If ``connect_redis`` has not been called yet.
    """
    if _redis is None:
        raise RuntimeError("Redis not initialised")
    return _redis

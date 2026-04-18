from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def connect_redis() -> None:
    """Create and store the global async Redis client.

    Must be called once during application startup before any call to
    :func:`get_redis`.
    """
    global _redis
    _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    """Close the global Redis connection gracefully.

    Safe to call even if the connection was never opened.
    """
    if _redis:
        await _redis.aclose()


def get_redis() -> Redis:
    """Return the active Redis client for use as a FastAPI dependency.

    Returns:
        The global async Redis instance.

    Raises:
        RuntimeError: If :func:`connect_redis` has not been called.
    """
    if _redis is None:
        raise RuntimeError("Redis not initialised — call connect_redis() first")
    return _redis

from redis.asyncio import Redis

from app.config import settings

RATE_LIMIT_TTL = 60  # seconds


async def check_rate_limit(redis: Redis, user_id: str) -> bool:
    """Return True if the user is within the rate limit, False if exceeded.

    Uses a fixed 60-second sliding window with a Redis counter.
    The key expires automatically after the window closes.
    """
    key = f"ratelimit:events:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_LIMIT_TTL)
    return count <= settings.RATE_LIMIT_PER_MINUTE

import uuid

from redis.asyncio import Redis

from app.config import settings


async def set_session(redis: Redis, user_id: str) -> str:
    """Create a new session and return the session_id."""
    session_id = str(uuid.uuid4())
    await redis.set(f"session:{session_id}", user_id, ex=settings.SESSION_TTL)
    return session_id


async def get_session(redis: Redis, session_id: str) -> str | None:
    """Return the user_id for a session, or None if expired/missing."""
    return await redis.get(f"session:{session_id}")


async def refresh_session(redis: Redis, session_id: str) -> None:
    """Reset TTL on an existing session (sliding window)."""
    await redis.expire(f"session:{session_id}", settings.SESSION_TTL)


async def delete_session(redis: Redis, session_id: str) -> None:
    """Destroy a session on logout."""
    await redis.delete(f"session:{session_id}")

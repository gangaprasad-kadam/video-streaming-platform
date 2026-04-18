"""
Session authentication helper for video-service.

Reads the HttpOnly session_id cookie and validates it against Redis.
Mirrors the pattern in shared/dependencies.py but uses this service's Redis client.
"""
from fastapi import Depends
from fastapi.requests import Request
from redis.asyncio import Redis

from app.redis_client import get_redis
from shared.exceptions import AuthError

_SESSION_TTL = 86400


async def get_current_user_id(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthError("Not authenticated")
    user_id = await redis.get(f"session:{session_id}")
    if not user_id:
        raise AuthError("Session expired or invalid")
    await redis.expire(f"session:{session_id}", _SESSION_TTL)
    return user_id.decode() if isinstance(user_id, bytes) else user_id

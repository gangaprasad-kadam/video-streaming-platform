"""
FastAPI dependency functions shared by every service.

Import and use with FastAPI's Depends() injection:

    from shared.dependencies import get_db, get_redis, get_current_user

    @router.get("/me")
    async def get_me(
        user_id: str = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        ...

Note: get_db and get_redis require the calling service to have set up
AsyncSessionLocal and redis_client in their own database.py / redis_client.py.
These are lazy imports — each service provides its own implementation.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from fastapi import Depends, Request
from redis.asyncio import Redis

from .exceptions import AuthError

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "86400"))


async def get_db() -> AsyncGenerator:
    """
    Yield a SQLAlchemy AsyncSession.
    The calling service must expose AsyncSessionLocal from its database.py.
    This dependency is meant to be overridden per service via FastAPI's dependency_overrides
    or by importing the service's own get_db after setup.

    Usage in a service's main.py:
        from app.database import get_db   # service-local version
        app.dependency_overrides[shared_get_db] = get_db
    """
    # Placeholder — each service overrides this with its own session factory
    raise NotImplementedError("get_db must be overridden by the service's database.py")
    # Correct implementation in each service:
    # async with AsyncSessionLocal() as session:
    #     yield session


async def get_redis() -> AsyncGenerator:
    """
    Yield a Redis connection.
    Each service overrides this with its own redis_client singleton.
    """
    raise NotImplementedError("get_redis must be overridden by the service's redis_client.py")


async def get_current_user(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> str:
    """
    Authenticate request via session cookie.

    1. Read 'session_id' HttpOnly cookie
    2. Look up Redis: session:{session_id} → user_id
    3. Refresh sliding TTL
    4. Return user_id (str UUID)

    Raises:
        AuthError: if cookie is missing or session is expired/invalid
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthError("No session cookie found. Please log in.")

    user_id = await redis.get(f"session:{session_id}")
    if not user_id:
        raise AuthError("Session expired or invalid. Please log in again.")

    # Sliding TTL: every authenticated request resets the 24h expiry
    await redis.expire(f"session:{session_id}", SESSION_TTL_SECONDS)

    return user_id.decode() if isinstance(user_id, bytes) else user_id

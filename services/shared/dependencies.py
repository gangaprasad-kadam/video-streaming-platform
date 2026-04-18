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
    """Yield a SQLAlchemy ``AsyncSession`` for the calling service.

    This is a placeholder that each service replaces via
    ``app.dependency_overrides`` or by importing its own ``get_db`` after
    setting up ``AsyncSessionLocal`` in ``database.py``.

    Yields:
        AsyncSession: An open database session scoped to the request.

    Raises:
        NotImplementedError: Always — until the service overrides this dependency.

    Example:
        In a service's ``main.py``::

            from app.database import get_db
            app.dependency_overrides[shared_get_db] = get_db
    """
    # Placeholder — each service overrides this with its own session factory
    raise NotImplementedError("get_db must be overridden by the service's database.py")
    # Correct implementation in each service:
    # async with AsyncSessionLocal() as session:
    #     yield session


async def get_redis() -> AsyncGenerator:
    """Yield a Redis connection for the calling service.

    Each service replaces this via ``app.dependency_overrides`` using its own
    ``redis_client`` singleton from ``redis_client.py``.

    Yields:
        Redis: An async Redis client instance.

    Raises:
        NotImplementedError: Always — until the service overrides this dependency.
    """
    raise NotImplementedError("get_redis must be overridden by the service's redis_client.py")


async def get_current_user(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> str:
    """Authenticate the incoming request using the session cookie.

    Reads the ``session_id`` HttpOnly cookie, validates it against Redis, and
    refreshes the sliding TTL so active users stay logged in.

    Args:
        request: The incoming FastAPI ``Request`` object, used to read cookies.
        redis: An async Redis client injected by ``get_redis``.

    Returns:
        The authenticated user's UUID as a plain string.

    Raises:
        AuthError: If the ``session_id`` cookie is absent, or if the session
            has expired or does not exist in Redis.
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

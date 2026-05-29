import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.auth.dao import repository as repo
from app.auth.utils.cache import delete_session, set_session
from app.auth.utils.schemas import LoginRequest, RegisterRequest
from app.exceptions import (
    EmailConflictError,
    InvalidCredentialsError,
    UsernameConflictError,
)
from app.models import User


def _hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        plain: The raw password string.

    Returns:
        A bcrypt-hashed password string.
    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash.

    Args:
        plain: The raw password to verify.
        hashed: The bcrypt hash to check against.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def register(db: AsyncSession, data: RegisterRequest) -> User:
    """Create a new user after checking for duplicate email and username.

    Args:
        db: Async database session.
        data: Registration payload with username, email, and password.

    Returns:
        The newly created User ORM object.

    Raises:
        EmailConflictError: If the email is already registered.
        UsernameConflictError: If the username is already taken.
    """
    if await repo.get_by_email(db, data.email):
        raise EmailConflictError()
    if await repo.get_by_username(db, data.username):
        raise UsernameConflictError()
    return await repo.create_user(
        db,
        username=data.username,
        email=data.email,
        password_hash=_hash_password(data.password),
    )


async def login(db: AsyncSession, redis: Redis, data: LoginRequest) -> str:
    """Verify credentials and return a new session_id."""
    user = await repo.get_by_email(db, data.email)
    if not user or not _verify_password(data.password, user.password_hash):
        raise InvalidCredentialsError()
    return await set_session(redis, str(user.id))


async def logout(redis: Redis, session_id: str) -> None:
    """Delete a session from Redis, effectively logging the user out.

    Args:
        redis: Redis client.
        session_id: The session identifier to invalidate.
    """
    await delete_session(redis, session_id)

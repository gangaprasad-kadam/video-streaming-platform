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
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def register(db: AsyncSession, data: RegisterRequest) -> User:
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
    await delete_session(redis, session_id)

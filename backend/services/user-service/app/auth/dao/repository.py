from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by their email address.

    Args:
        db: Async database session.
        email: Email address to look up.

    Returns:
        The matching User, or None if not found.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    """Fetch a user by their username.

    Args:
        db: Async database session.
        username: Username to look up.

    Returns:
        The matching User, or None if not found.
    """
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, username: str, email: str, password_hash: str) -> User:
    """Insert a new user row and return the persisted object.

    Args:
        db: Async database session.
        username: Desired username.
        email: User's email address.
        password_hash: Bcrypt-hashed password.

    Returns:
        The newly created and refreshed User ORM object.
    """
    user = User(username=username, email=email, password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

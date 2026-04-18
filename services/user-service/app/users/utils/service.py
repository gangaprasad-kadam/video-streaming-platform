from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import UserNotFoundError
from app.models import User
from app.users.dao import repository as repo


async def get_me(db: AsyncSession, user_id: str) -> User:
    user = await repo.get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError()
    return user

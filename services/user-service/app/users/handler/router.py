from fastapi import APIRouter, Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.auth.utils.cache import get_session, refresh_session
from app.database import get_db
from app.redis_client import get_redis
from app.users.utils import service as users_service
from app.users.utils.schemas import UserProfileResponse
from shared.exceptions import AuthError
from shared.schemas import SuccessResponse

router = APIRouter(prefix="/users", tags=["users"])


async def _get_current_user_id(
    request: Request, redis: Redis = Depends(get_redis)
) -> str:
    """Extract and validate the session cookie, returning the user's ID.

    Args:
        request: Incoming HTTP request containing the session cookie.
        redis: Redis client (injected).

    Returns:
        The authenticated user's ID string.

    Raises:
        AuthError: If the session cookie is missing or the session has expired.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthError("Not authenticated")
    user_id = await get_session(redis, session_id)
    if not user_id:
        raise AuthError("Session expired or invalid")
    await refresh_session(redis, session_id)
    return user_id


@router.get("/me", response_model=SuccessResponse[UserProfileResponse])
async def get_me(
    user_id: str = Depends(_get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await users_service.get_me(db, user_id)
    return SuccessResponse(
        data=UserProfileResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat(),
        )
    )

from fastapi import APIRouter, Depends, Response
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.auth.utils import service as auth_service
from app.auth.utils.cache import get_session, refresh_session
from app.auth.utils.schemas import LoginRequest, RegisterRequest, UserResponse
from app.database import get_db
from app.exceptions import InvalidCredentialsError
from app.redis_client import get_redis
from shared.exceptions import AuthError
from shared.schemas import SuccessResponse

router = APIRouter(prefix="/auth", tags=["auth"])


async def _require_session(request: Request, redis: Redis = Depends(get_redis)) -> tuple[str, str]:
    """Return (session_id, user_id) or raise AuthError."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthError("Not authenticated")
    user_id = await get_session(redis, session_id)
    if not user_id:
        raise AuthError("Session expired or invalid")
    await refresh_session(redis, session_id)
    return session_id, user_id


@router.post("/register", status_code=201, response_model=SuccessResponse[UserResponse])
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account.

    Args:
        data: Username, email, and password for the new account.
        db: Async database session (injected).

    Returns:
        SuccessResponse containing the created user's public profile.

    Raises:
        ConflictError: If the email or username is already taken.
    """
    user = await auth_service.register(db, data)
    return SuccessResponse(
        data=UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat(),
        )
    )


@router.post("/login", response_model=SuccessResponse[dict])
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Authenticate a user and issue a session cookie.

    Args:
        data: Email and password credentials.
        response: FastAPI response object used to set the cookie.
        db: Async database session (injected).
        redis: Redis client (injected).

    Returns:
        SuccessResponse with a confirmation message. Sets an HttpOnly
        ``session_id`` cookie on the response.

    Raises:
        InvalidCredentialsError: If the email or password is wrong.
    """
    session_id = await auth_service.login(db, redis, data)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return SuccessResponse(data={"message": "logged in"})


@router.post("/logout", response_model=SuccessResponse[dict])
async def logout(
    response: Response,
    redis: Redis = Depends(get_redis),
    session: tuple = Depends(_require_session),
):
    """Invalidate the current session and clear the session cookie.

    Args:
        response: FastAPI response object used to delete the cookie.
        redis: Redis client (injected).
        session: Validated (session_id, user_id) pair from ``_require_session``.

    Returns:
        SuccessResponse with a confirmation message.

    Raises:
        AuthError: If no valid session cookie is present.
    """
    session_id, _ = session
    await auth_service.logout(redis, session_id)
    response.delete_cookie("session_id")
    return SuccessResponse(data={"message": "logged out"})

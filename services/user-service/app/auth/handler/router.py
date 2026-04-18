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
    session_id, _ = session
    await auth_service.logout(redis, session_id)
    response.delete_cookie("session_id")
    return SuccessResponse(data={"message": "logged out"})

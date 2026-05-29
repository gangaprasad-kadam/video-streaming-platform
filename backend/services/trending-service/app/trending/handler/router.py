from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis_client import get_redis
from app.trending.utils import service as trending_service
from app.trending.utils.schemas import RecommendationsResponse, TrendingResponse
from shared.schemas import SuccessResponse

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("", response_model=SuccessResponse[TrendingResponse])
async def get_trending(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Return the top trending videos ranked by weighted interaction score.

    Scores are stored in a Redis sorted set and decay by 10% every hour.
    Only ``ready`` videos are included in the response.
    """
    result = await trending_service.get_trending(db, redis, limit)
    return SuccessResponse(data=result)


@router.get(
    "/recommendations/{user_id}",
    response_model=SuccessResponse[RecommendationsResponse],
)
async def get_recommendations(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Return a personalised recommendation list for a user.

    Blends 60% trending content (unwatched) with 40% videos from creators
    the user has previously watched.
    """
    result = await trending_service.get_recommendations(db, redis, user_id, limit)
    return SuccessResponse(data=result)

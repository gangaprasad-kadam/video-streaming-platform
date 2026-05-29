from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis_client import get_redis
from app.summary.utils import service as summary_service
from app.summary.utils.schemas import SummaryResponse
from shared.schemas import SuccessResponse

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/{video_id}", response_model=SuccessResponse[SummaryResponse])
async def get_summary(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Return AI-generated transcript, summary, and key moments for a video.

    Checks Redis first (1-hour TTL) before falling back to PostgreSQL.
    Returns 404 if no summary has been generated yet.

    Args:
        video_id: UUID string of the video.
        db: Injected async database session.
        redis: Injected Redis client.

    Returns:
        SuccessResponse wrapping a SummaryResponse payload.
    """
    result = await summary_service.get_summary(db, redis, video_id)
    return SuccessResponse(data=result)

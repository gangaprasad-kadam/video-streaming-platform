from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

from app.heatmap.utils import service as heatmap_service
from app.heatmap.utils.schemas import HeatmapResponse, HighlightsResponse
from app.mongo_client import get_db
from app.redis_client import get_redis
from shared.schemas import SuccessResponse

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


@router.get("/{video_id}", response_model=SuccessResponse[HeatmapResponse])
async def get_heatmap(
    video_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return the all-time heatmap for a video.

    Reads from MongoDB ``heatmap_buckets`` collection. Returns all 5-second
    buckets with their cumulative engagement score.

    Raises 404 if no interaction data has been recorded for this video.
    """
    result = await heatmap_service.get_heatmap(db, video_id)
    return SuccessResponse(data=result)


@router.get("/{video_id}/live", response_model=SuccessResponse[HeatmapResponse])
async def get_live_heatmap(
    video_id: str,
    redis: Redis = Depends(get_redis),
):
    """Return the live (last 5-minute) heatmap for a video.

    Reads from Redis live keys (TTL 300s). Returns empty bucket list if no
    recent activity — this is not an error.
    """
    result = await heatmap_service.get_live_heatmap(redis, video_id)
    return SuccessResponse(data=result)


@router.get("/{video_id}/highlights", response_model=SuccessResponse[HighlightsResponse])
async def get_highlights(
    video_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return the top N most-replayed segments for a video.

    Ranked by cumulative score descending. Useful for creator dashboards
    and surfacing the 'best moments' to viewers.

    Raises 404 if no interaction data exists.
    """
    result = await heatmap_service.get_highlights(db, video_id, limit)
    return SuccessResponse(data=result)

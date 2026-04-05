from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.requests import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import get_current_user_id
from app.database import get_db
from app.redis_client import get_redis
from app.videos import service as video_service
from app.videos.schemas import (
    InternalStatusUpdateRequest,
    VideoResponse,
    VideoStatusResponse,
    VideoUpdateRequest,
)
from shared.schemas import PagedResponse, SuccessResponse

router = APIRouter(prefix="/videos", tags=["videos"])
internal_router = APIRouter(prefix="/internal/videos", tags=["internal"])


@router.post("/upload", status_code=201, response_model=SuccessResponse[VideoResponse])
async def upload_video(
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    video = await video_service.upload_video(db, redis, file, title, description, user_id)
    return SuccessResponse(data=video_service._to_response(video))


@router.get("/{video_id}", response_model=SuccessResponse[VideoResponse])
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    video = await video_service.get_video(db, redis, video_id)
    return SuccessResponse(data=video)


@router.get("", response_model=PagedResponse[VideoResponse])
async def list_videos(
    page: int = 1,
    limit: int = 20,
    creator_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await video_service.list_videos(db, page=page, limit=limit, creator_id=creator_id)
    return PagedResponse(
        data=[video_service._to_response(v) for v in result.items],
        total=result.total,
        page=page,
        page_size=limit,
    )


@router.patch("/{video_id}", response_model=SuccessResponse[VideoResponse])
async def patch_video(
    video_id: str,
    data: VideoUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    video = await video_service.patch_video(db, redis, video_id, user_id, data.title, data.description)
    return SuccessResponse(data=video)


@router.get("/{video_id}/status", response_model=SuccessResponse[VideoStatusResponse])
async def get_status(video_id: str, db: AsyncSession = Depends(get_db)):
    from app.videos.repository import get_by_id
    from app.exceptions import VideoNotFoundError
    video = await get_by_id(db, video_id)
    if not video:
        raise VideoNotFoundError(video_id)
    return SuccessResponse(data=VideoStatusResponse(id=str(video.id), status=video.status.value))


@internal_router.patch("/{video_id}/status", response_model=SuccessResponse[VideoResponse])
async def internal_update_status(
    video_id: str,
    data: InternalStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    video = await video_service.update_status(
        db, redis, video_id, data.status, data.hls_path, data.thumbnail_path, data.duration
    )
    return SuccessResponse(data=video)

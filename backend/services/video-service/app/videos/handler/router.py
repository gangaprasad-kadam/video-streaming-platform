from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.requests import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import get_current_user_id
from app.database import get_db
from app.exceptions import VideoNotFoundError
from app.redis_client import get_redis
from app.videos.dao.repository import (
    get_by_id,
    get_ready_videos_by_creators,
    get_ready_videos_by_ids,
    get_video_stream_info,
)
from app.videos.utils import service as video_service
from app.videos.utils.schemas import (
    InternalStatusUpdateRequest,
    StreamInfoResponse,
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
    tags: str | None = Form(None),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Upload a new video file.

    Saves the file to disk, creates a DB record, and publishes a
    ``video.uploaded`` Kafka event to trigger the processing pipeline.

    Args:
        title: Human-readable title for the video.
        description: Optional description text.
        tags: Comma-separated tag strings (e.g. ``"tech,tutorial"``).
        file: Multipart video file upload.
        user_id: ID of the authenticated uploader (from session cookie).
        db: Async database session.
        redis: Async Redis client.

    Returns:
        SuccessResponse wrapping the newly created VideoResponse.
    """
    parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    video = await video_service.upload_video(db, redis, file, title, description, user_id, tags=parsed_tags)
    return SuccessResponse(data=video_service._to_response(video))


@router.get("/{video_id}", response_model=SuccessResponse[VideoResponse])
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Fetch a single video by ID.

    Checks Redis cache first; falls back to PostgreSQL on a cache miss.

    Args:
        video_id: UUID string of the video to retrieve.
        db: Async database session.
        redis: Async Redis client.

    Returns:
        SuccessResponse wrapping VideoResponse.

    Raises:
        VideoNotFoundError: If no video with the given ID exists.
    """
    video = await video_service.get_video(db, redis, video_id)
    return SuccessResponse(data=video)


@router.get("", response_model=PagedResponse[VideoResponse])
async def list_videos(
    page: int = 1,
    limit: int = 20,
    creator_id: str | None = None,
    q: str | None = Query(default=None, description="Case-insensitive title search"),
    db: AsyncSession = Depends(get_db),
):
    """List videos with optional creator filter, title search, and pagination.

    Args:
        page: 1-based page number.
        limit: Maximum number of results per page.
        creator_id: Optional UUID string to filter by creator.
        q: Optional title substring search (case-insensitive).
        db: Async database session.

    Returns:
        PagedResponse containing a list of VideoResponse objects plus
        total count, current page, and page size.
    """
    result = await video_service.list_videos(db, page=page, limit=limit, creator_id=creator_id, q=q)
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
    """Update a video's title or description (creator only).

    Only the video's creator may call this endpoint. Invalidates the
    Redis cache entry for the video on success.

    Args:
        video_id: UUID string of the video to update.
        data: Fields to update (title and/or description).
        user_id: ID of the authenticated user (from session cookie).
        db: Async database session.
        redis: Async Redis client.

    Returns:
        SuccessResponse wrapping the updated VideoResponse.

    Raises:
        VideoNotFoundError: If the video does not exist.
        VideoForbiddenError: If the requester is not the creator.
    """
    video = await video_service.patch_video(db, redis, video_id, user_id, data.title, data.description, data.tags)
    return SuccessResponse(data=video)


@router.delete("/{video_id}", status_code=204)
async def delete_video(
    video_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Delete a video and its associated files (creator only).

    Args:
        video_id: UUID string of the video to delete.
        user_id: ID of the authenticated user (from session cookie).
        db: Async database session.
        redis: Async Redis client.

    Raises:
        VideoNotFoundError: If the video does not exist.
        VideoForbiddenError: If the requester is not the creator.
    """
    await video_service.delete_video(db, redis, video_id, user_id)


@router.get("/{video_id}/status", response_model=SuccessResponse[VideoStatusResponse])
async def get_status(video_id: str, db: AsyncSession = Depends(get_db)):
    """Return the processing status of a video.

    Lightweight polling endpoint that bypasses the cache so callers
    always get the latest lifecycle state.

    Args:
        video_id: UUID string of the video to check.
        db: Async database session.

    Returns:
        SuccessResponse wrapping VideoStatusResponse with id and status.

    Raises:
        VideoNotFoundError: If no video with the given ID exists.
    """
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
    """Internal endpoint for workers to advance a video's lifecycle status.

    Called by ``encoding-worker`` and ``thumbnail-worker`` after processing.
    Not exposed through the public NGINX gateway.

    Args:
        video_id: UUID string of the video being updated.
        data: New status plus optional HLS path, thumbnail path, and duration.
        db: Async database session.
        redis: Async Redis client (cache is invalidated on update).

    Returns:
        SuccessResponse wrapping the updated VideoResponse.

    Raises:
        VideoNotFoundError: If the video does not exist.
    """
    video = await video_service.update_status(
        db, redis, video_id, data.status, data.hls_path, data.thumbnail_path, data.duration
    )
    return SuccessResponse(data=video)


@internal_router.get("/batch", response_model=SuccessResponse[list[VideoResponse]])
async def batch_get_videos(
    ids: str = Query(..., description="Comma-separated list of video UUIDs"),
    db: AsyncSession = Depends(get_db),
):
    """Fetch multiple ready videos by ID in a single request.

    Used by the trending-service to enrich trending scores with video metadata
    without querying the database directly.

    Args:
        ids: Comma-separated video UUID strings.
        db: Async database session.

    Returns:
        SuccessResponse wrapping a list of VideoResponse objects (only ``ready`` videos).
    """
    video_ids = [vid.strip() for vid in ids.split(",") if vid.strip()]
    videos = await get_ready_videos_by_ids(db, video_ids)
    return SuccessResponse(data=[video_service._to_response(v) for v in videos])


@internal_router.get("/by-creators", response_model=SuccessResponse[list[VideoResponse]])
async def get_videos_by_creators(
    creator_ids: str = Query(..., description="Comma-separated creator UUIDs"),
    exclude_ids: str = Query(default="", description="Comma-separated video UUIDs to exclude"),
    limit: int = Query(default=40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Fetch ready videos from specific creators, excluding given video IDs.

    Used by the trending-service to build the creator-based recommendation slice.

    Args:
        creator_ids: Comma-separated creator UUID strings.
        exclude_ids: Comma-separated video UUIDs to exclude (already watched / trending picks).
        limit: Maximum number of results to return.
        db: Async database session.

    Returns:
        SuccessResponse wrapping a list of VideoResponse objects.
    """
    c_ids = [cid.strip() for cid in creator_ids.split(",") if cid.strip()]
    e_ids = [vid.strip() for vid in exclude_ids.split(",") if vid.strip()]
    videos = await get_ready_videos_by_creators(db, c_ids, e_ids, limit=limit)
    return SuccessResponse(data=[video_service._to_response(v) for v in videos])


@internal_router.get("/{video_id}/stream-info", response_model=SuccessResponse[StreamInfoResponse])
async def get_stream_info(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return HLS path and status for a ready video.

    Used by streaming-service for strict API isolation — avoids direct DB access.

    Args:
        video_id: UUID string of the target video.
        db: Async database session.

    Returns:
        SuccessResponse wrapping StreamInfoResponse, or 404 if not ready.
    """
    video = await get_video_stream_info(db, video_id)
    if not video:
        raise VideoNotFoundError(video_id)
    return SuccessResponse(data=StreamInfoResponse(
        id=str(video.id),
        status=video.status.value,
        hls_path=video.hls_path,
    ))

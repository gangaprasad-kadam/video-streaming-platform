import os
import uuid

import aiofiles
from fastapi import UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import kafka_producer
from app.config import settings
from app.exceptions import VideoForbiddenError, VideoNotFoundError
from app.models import Video
from app.videos.dao import repository as repo
from app.videos.utils.cache import cache_video_meta, get_cached_video, invalidate_video_cache
from app.videos.dao.repository import VideoPage
from app.videos.utils.schemas import VideoResponse


def _to_response(video: Video) -> VideoResponse:
    """Convert a Video ORM instance to a VideoResponse schema.

    Args:
        video: SQLAlchemy Video model instance.

    Returns:
        VideoResponse with all fields serialised to primitive types.
    """
    return VideoResponse(
        id=str(video.id),
        title=video.title,
        description=video.description,
        status=video.status.value,
        creator_id=str(video.creator_id),
        file_path=video.file_path,
        hls_path=video.hls_path,
        thumbnail_path=video.thumbnail_path,
        duration=float(video.duration) if video.duration is not None else None,
        file_size_bytes=video.file_size_bytes,
        mime_type=video.mime_type,
        created_at=video.created_at.isoformat(),
    )


async def upload_video(
    db: AsyncSession,
    redis: Redis,
    file: UploadFile,
    title: str,
    description: str | None,
    creator_id: str,
) -> Video:
    """Save an uploaded video file and create its database record.

    Writes the file to ``MEDIA_ROOT/uploads/``, renames it to the
    real UUID after the DB row is created, then publishes a
    ``video.uploaded`` Kafka event.

    Args:
        db: Async database session.
        redis: Async Redis client (reserved for future cache ops).
        file: Incoming multipart file from the HTTP request.
        title: Title for the video.
        description: Optional description for the video.
        creator_id: UUID string of the uploading user.

    Returns:
        The newly created Video ORM instance.
    """
    video_id_placeholder = uuid.uuid4()
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    file_path = os.path.join(settings.MEDIA_ROOT, "uploads", f"{video_id_placeholder}{ext}")

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    video = await repo.create_video(
        db,
        title=title,
        description=description,
        creator_id=creator_id,
        file_path=file_path,
        file_size_bytes=len(content),
        mime_type=file.content_type,
    )

    # rename file to actual video UUID
    final_path = os.path.join(settings.MEDIA_ROOT, "uploads", f"{video.id}{ext}")
    os.rename(file_path, final_path)
    video.file_path = final_path
    await db.commit()
    await db.refresh(video)

    await kafka_producer.publish(
        topic="video.uploaded",
        key=str(video.id),
        value={
            "videoId": str(video.id),
            "creatorId": str(video.creator_id),
            "filePath": video.file_path,
            "mimeType": video.mime_type,
            "title": video.title,
            "uploadedAt": video.created_at.isoformat(),
        },
    )
    return video


async def get_video(db: AsyncSession, redis: Redis, video_id: str) -> VideoResponse:
    """Retrieve a video by ID using a cache-aside strategy.

    Checks Redis first; on a miss, fetches from PostgreSQL and
    populates the cache with a 5-minute TTL.

    Args:
        db: Async database session.
        redis: Async Redis client.
        video_id: UUID string of the video.

    Returns:
        VideoResponse for the requested video.

    Raises:
        VideoNotFoundError: If no video with the given ID exists.
    """
    cached = await get_cached_video(redis, video_id)
    if cached:
        return VideoResponse(**cached)

    video = await repo.get_by_id(db, video_id)
    if not video:
        raise VideoNotFoundError(video_id)

    response = _to_response(video)
    await cache_video_meta(redis, video_id, response.model_dump())
    return response


async def list_videos(
    db: AsyncSession, page: int, limit: int, creator_id: str | None
) -> VideoPage:
    """Return a paginated list of videos.

    Delegates directly to the repository layer. Optionally filters
    results to a single creator.

    Args:
        db: Async database session.
        page: 1-based page number.
        limit: Maximum number of items per page.
        creator_id: Optional UUID string to restrict results to one creator.

    Returns:
        VideoPage containing matched Video ORM instances and total count.
    """
    return await repo.list_videos(db, page=page, limit=limit, creator_id=creator_id)


async def patch_video(
    db: AsyncSession,
    redis: Redis,
    video_id: str,
    requester_id: str,
    title: str | None,
    description: str | None,
) -> VideoResponse:
    video = await repo.get_by_id(db, video_id)
    if not video:
        raise VideoNotFoundError(video_id)
    if str(video.creator_id) != requester_id:
        raise VideoForbiddenError()

    video = await repo.update_video(db, video, title=title, description=description)
    await invalidate_video_cache(redis, video_id)
    return _to_response(video)


async def update_status(
    db: AsyncSession,
    redis: Redis,
    video_id: str,
    new_status: str,
    hls_path: str | None = None,
    thumbnail_path: str | None = None,
    duration: float | None = None,
) -> VideoResponse:
    video = await repo.get_by_id(db, video_id)
    if not video:
        raise VideoNotFoundError(video_id)

    # In terminal state: update metadata fields without changing status
    if video.status.value in ("ready", "failed"):
        if any(v is not None for v in (hls_path, thumbnail_path, duration)):
            video = await repo.update_video_fields(db, video, hls_path=hls_path, thumbnail_path=thumbnail_path, duration=duration)
            await invalidate_video_cache(redis, video_id)
        return _to_response(video)

    video = await repo.update_status(db, video, new_status, hls_path, thumbnail_path, duration)
    await invalidate_video_cache(redis, video_id)
    return _to_response(video)

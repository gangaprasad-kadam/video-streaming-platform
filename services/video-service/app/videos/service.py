import os

import aiofiles
from fastapi import UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import kafka_producer
from app.config import settings
from app.exceptions import VideoForbiddenError, VideoNotFoundError
from app.models import Video
from app.videos import repository as repo
from app.videos.cache import cache_video_meta, get_cached_video, invalidate_video_cache
from app.videos.repository import VideoPage
from app.videos.schemas import VideoResponse


def _to_response(video: Video) -> VideoResponse:
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
    video_id_placeholder = __import__("uuid").uuid4()
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

    # Idempotency: skip if already in terminal state
    if video.status.value in ("ready", "failed"):
        return _to_response(video)

    video = await repo.update_status(db, video, new_status, hls_path, thumbnail_path, duration)
    await invalidate_video_cache(redis, video_id)
    return _to_response(video)

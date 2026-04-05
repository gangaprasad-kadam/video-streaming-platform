import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStatus


@dataclass
class VideoPage:
    items: list[Video]
    total: int


async def create_video(
    db: AsyncSession,
    title: str,
    description: str | None,
    creator_id: str,
    file_path: str,
    file_size_bytes: int | None,
    mime_type: str | None,
) -> Video:
    video = Video(
        title=title,
        description=description,
        creator_id=uuid.UUID(creator_id),
        file_path=file_path,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        status=VideoStatus.uploading,
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


async def get_by_id(db: AsyncSession, video_id: str) -> Video | None:
    result = await db.execute(select(Video).where(Video.id == uuid.UUID(video_id)))
    return result.scalar_one_or_none()


async def list_videos(
    db: AsyncSession, page: int, limit: int, creator_id: str | None = None
) -> VideoPage:
    query = select(Video)
    count_query = select(func.count()).select_from(Video)
    if creator_id:
        uid = uuid.UUID(creator_id)
        query = query.where(Video.creator_id == uid)
        count_query = count_query.where(Video.creator_id == uid)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Video.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return VideoPage(items=list(result.scalars().all()), total=total)


async def update_video(db: AsyncSession, video: Video, title: str | None, description: str | None) -> Video:
    if title is not None:
        video.title = title
    if description is not None:
        video.description = description
    await db.commit()
    await db.refresh(video)
    return video


async def update_status(
    db: AsyncSession,
    video: Video,
    new_status: str,
    hls_path: str | None = None,
    thumbnail_path: str | None = None,
    duration: float | None = None,
) -> Video:
    video.status = VideoStatus(new_status)
    if hls_path is not None:
        video.hls_path = hls_path
    if thumbnail_path is not None:
        video.thumbnail_path = thumbnail_path
    if duration is not None:
        video.duration = duration
    await db.commit()
    await db.refresh(video)
    return video

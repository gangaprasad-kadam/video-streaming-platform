import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStatus


@dataclass
class VideoPage:
    """Result container for paginated video queries.

    Attributes:
        items: List of Video ORM instances for the current page.
        total: Total number of matching videos across all pages.
    """

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
    """Insert a new Video row with status ``uploading``.

    Args:
        db: Async database session.
        title: Video title.
        description: Optional description.
        creator_id: UUID string of the creator.
        file_path: Filesystem path where the raw upload is stored.
        file_size_bytes: Upload size in bytes, or ``None`` if unknown.
        mime_type: MIME type of the uploaded file, or ``None`` if unknown.

    Returns:
        The newly persisted Video ORM instance.
    """
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


async def get_video_stream_info(db: AsyncSession, video_id: str) -> Video | None:
    """Fetch a video only when status is ``ready`` (for streaming-service use).

    Args:
        db: Async database session.
        video_id: UUID string of the video.

    Returns:
        Video ORM instance if found and ready, or ``None`` otherwise.
    """
    result = await db.execute(
        select(Video).where(
            Video.id == uuid.UUID(video_id),
            Video.status == VideoStatus.ready,
        )
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, video_id: str) -> Video | None:
    """Fetch a single Video by its UUID.

    Args:
        db: Async database session.
        video_id: UUID string of the video.

    Returns:
        Matching Video ORM instance, or ``None`` if not found.
    """
    result = await db.execute(select(Video).where(Video.id == uuid.UUID(video_id)))
    return result.scalar_one_or_none()


async def list_videos(
    db: AsyncSession, page: int, limit: int, creator_id: str | None = None
) -> VideoPage:
    """Return a page of Video rows ordered by creation date (newest first).

    Args:
        db: Async database session.
        page: 1-based page number.
        limit: Maximum number of rows to return.
        creator_id: Optional UUID string to filter by a specific creator.

    Returns:
        VideoPage with the matching items and the total unfiltered count.
    """
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


async def get_ready_videos_by_ids(
    db: AsyncSession, video_ids: list[str]
) -> list[Video]:
    """Fetch ready Video rows for the given list of UUIDs.

    Args:
        db: Async database session.
        video_ids: List of video UUID strings to look up.

    Returns:
        List of Video ORM instances that exist and have status ``ready``.
    """
    if not video_ids:
        return []
    uuids = [uuid.UUID(vid) for vid in video_ids]
    result = await db.execute(
        select(Video).where(Video.id.in_(uuids), Video.status == VideoStatus.ready)
    )
    return list(result.scalars().all())


async def get_ready_videos_by_creators(
    db: AsyncSession,
    creator_ids: list[str],
    exclude_video_ids: list[str],
    limit: int = 40,
) -> list[Video]:
    """Fetch ready videos from specific creators, excluding given video IDs.

    Args:
        db: Async database session.
        creator_ids: List of creator UUID strings to query.
        exclude_video_ids: Video IDs to exclude.
        limit: Maximum number of rows to return.

    Returns:
        List of up to ``limit`` Video ORM instances.
    """
    if not creator_ids:
        return []
    c_uuids = [uuid.UUID(cid) for cid in creator_ids]
    stmt = select(Video).where(
        Video.creator_id.in_(c_uuids),
        Video.status == VideoStatus.ready,
    )
    if exclude_video_ids:
        e_uuids = [uuid.UUID(vid) for vid in exclude_video_ids]
        stmt = stmt.where(Video.id.notin_(e_uuids))
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_video(db: AsyncSession, video: Video, title: str | None, description: str | None) -> Video:
    """Update a video's title and/or description in place.

    Only non-``None`` arguments are applied, so callers can pass ``None``
    to leave a field unchanged.

    Args:
        db: Async database session.
        video: Video ORM instance to modify.
        title: New title, or ``None`` to keep the existing value.
        description: New description, or ``None`` to keep the existing value.

    Returns:
        The updated and refreshed Video ORM instance.
    """
    if title is not None:
        video.title = title
    if description is not None:
        video.description = description
    await db.commit()
    await db.refresh(video)
    return video


async def update_video_fields(
    db: AsyncSession,
    video: Video,
    hls_path: str | None = None,
    thumbnail_path: str | None = None,
    duration: float | None = None,
) -> Video:
    """Update metadata fields without changing status (used for terminal-state partial updates)."""
    if hls_path is not None:
        video.hls_path = hls_path
    if thumbnail_path is not None:
        video.thumbnail_path = thumbnail_path
    if duration is not None:
        video.duration = duration
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
    """Update a video's status and optionally set processing-result fields.

    Args:
        db: Async database session.
        video: Video ORM instance to modify.
        new_status: Target status string (must be a valid ``VideoStatus`` value).
        hls_path: Path to the generated HLS playlist, if available.
        thumbnail_path: Path to the generated thumbnail, if available.
        duration: Video duration in seconds, if known.

    Returns:
        The updated and refreshed Video ORM instance.
    """
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

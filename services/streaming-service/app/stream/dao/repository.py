import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStatus


async def get_ready_video(db: AsyncSession, video_id: str) -> Video | None:
    """Fetch a video record only when its status is ``ready``.

    Args:
        db: Active async database session.
        video_id: UUID string of the video to look up.

    Returns:
        The ``Video`` ORM object if found and ready, or ``None`` otherwise.
    """
    result = await db.execute(
        select(Video).where(
            Video.id == uuid.UUID(video_id),
            Video.status == VideoStatus.ready,
        )
    )
    return result.scalar_one_or_none()

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStatus


async def get_ready_video(db: AsyncSession, video_id: str) -> Video | None:
    """Fetch a video only if it has status=ready. Returns None otherwise."""
    result = await db.execute(
        select(Video).where(
            Video.id == uuid.UUID(video_id),
            Video.status == VideoStatus.ready,
        )
    )
    return result.scalar_one_or_none()

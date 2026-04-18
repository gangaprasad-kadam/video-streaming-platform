import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoSummary


async def get_by_video_id(db: AsyncSession, video_id: str) -> VideoSummary | None:
    result = await db.execute(
        select(VideoSummary).where(VideoSummary.video_id == uuid.UUID(video_id))
    )
    return result.scalar_one_or_none()


async def create_summary(
    db: AsyncSession,
    video_id: str,
    transcript: str,
    summary: str,
    key_moments: list[dict],
) -> VideoSummary:
    record = VideoSummary(
        video_id=uuid.UUID(video_id),
        transcript=transcript,
        summary=summary,
        key_moments=key_moments,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record

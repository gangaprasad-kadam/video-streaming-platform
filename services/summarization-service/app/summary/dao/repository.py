import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoSummary


async def get_by_video_id(db: AsyncSession, video_id: str) -> VideoSummary | None:
    """Fetch a summary record by video ID.

    Args:
        db: Active async database session.
        video_id: UUID string of the video.

    Returns:
        The ``VideoSummary`` ORM object if found, or ``None``.
    """
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
    """Persist a new summary record to the database.

    Args:
        db: Active async database session.
        video_id: UUID string of the video.
        transcript: Full text transcript produced by Whisper.
        summary: Condensed summary produced by BART.
        key_moments: List of key moment dicts (``timestamp``, ``label``).

    Returns:
        The newly created ``VideoSummary`` ORM object (refreshed from DB).
    """
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

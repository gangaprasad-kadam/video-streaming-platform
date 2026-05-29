import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WatchHistory


async def get_watch_history(db: AsyncSession, user_id: str) -> list[WatchHistory]:
    """Return all watch history rows for a user.

    Args:
        db: Active async database session.
        user_id: UUID string of the user.

    Returns:
        List of WatchHistory ORM objects.
    """
    result = await db.execute(
        select(WatchHistory).where(WatchHistory.user_id == uuid.UUID(user_id))
    )
    return list(result.scalars().all())


async def upsert_watch_history(
    db: AsyncSession, user_id: str, video_id: str, creator_id: str
) -> None:
    """Insert or update a watch history record.

    Args:
        db: Active async database session.
        user_id: UUID string of the user.
        video_id: UUID string of the video.
        creator_id: UUID string of the video creator.
    """
    uid = uuid.UUID(user_id)
    vid = uuid.UUID(video_id)
    cid = uuid.UUID(creator_id)

    result = await db.execute(
        select(WatchHistory).where(
            WatchHistory.user_id == uid,
            WatchHistory.video_id == vid,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        db.add(WatchHistory(user_id=uid, video_id=vid, creator_id=cid))
    await db.commit()

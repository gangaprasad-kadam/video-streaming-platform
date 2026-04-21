import uuid
from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WatchHistory(Base):
    """Tracks which videos a user has watched.

    Used by the recommendations engine to filter out already-seen content
    and to identify creator preferences for the 40% creator-based slice.
    This is trending-service's own data — it is NOT shared with other services.
    """

    __tablename__ = "watch_history"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uq_user_video"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    # creator_id is denormalised here so we don't need to call video-service for recommendations
    creator_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    watched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

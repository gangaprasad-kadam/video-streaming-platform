from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrendingVideoItem(BaseModel):
    """A single video entry in the trending leaderboard."""

    video_id: str
    title: str
    creator_id: str
    thumbnail_path: str | None
    duration: float | None
    score: float
    rank: int


class TrendingResponse(BaseModel):
    """Response envelope for the trending endpoint."""

    videos: list[TrendingVideoItem]
    total: int


class RecommendationItem(BaseModel):
    """A single recommended video with the reason it was recommended."""

    video_id: str
    title: str
    creator_id: str
    thumbnail_path: str | None
    duration: float | None
    reason: str  # "trending" | "creator"


class RecommendationsResponse(BaseModel):
    """Response envelope for the recommendations endpoint."""

    user_id: str
    videos: list[RecommendationItem]
    total: int


class InteractionEvent(BaseModel):
    """Schema for a viewer interaction event consumed from Kafka.

    Published by the event-ingestion service (Phase 8a) or clients directly.
    """

    userId: str
    videoId: str
    action: str  # PLAY | WATCH_COMPLETE | REWIND | SEEK | PAUSE | SKIP
    videoTs: float = 0.0
    creatorId: str = ""
    sessionId: str = ""
    timestamp: str = ""

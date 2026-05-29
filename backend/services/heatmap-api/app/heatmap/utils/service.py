from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

from app.config import settings
from app.heatmap.dao import repository as repo
from app.heatmap.utils.schemas import BucketItem, HeatmapResponse, HighlightsResponse, make_label
from shared.exceptions import NotFoundError


async def get_heatmap(
    db: AsyncIOMotorDatabase,
    video_id: str,
) -> HeatmapResponse:
    """Return the all-time heatmap for a video from MongoDB.

    Raises NotFoundError if no heatmap data exists for the video.
    """
    rows = await repo.get_all_buckets(db, video_id)
    if not rows:
        raise NotFoundError("heatmap")

    buckets = [
        BucketItem(
            bucket=r["bucket"],
            score=r["score"],
            label=make_label(r["bucket"], settings.BUCKET_SIZE),
        )
        for r in rows
    ]
    return HeatmapResponse(
        video_id=video_id,
        bucket_size=settings.BUCKET_SIZE,
        total_buckets=len(buckets),
        buckets=buckets,
    )


async def get_live_heatmap(
    redis: Redis,
    video_id: str,
) -> HeatmapResponse:
    """Return the live (last 5-minute) heatmap from Redis.

    Scans all ``heatmap:{videoId}:live:*`` keys. Returns empty buckets list
    if no recent activity exists (not an error — just no recent views).
    """
    pattern = f"heatmap:{video_id}:live:*"
    keys = await redis.keys(pattern)

    buckets: list[BucketItem] = []
    for key in sorted(keys):
        raw_score = await redis.get(key)
        if raw_score is None:
            continue
        bucket_sec = int(key.split(":")[-1])
        buckets.append(BucketItem(
            bucket=bucket_sec,
            score=int(raw_score),
            label=make_label(bucket_sec, settings.BUCKET_SIZE),
        ))

    return HeatmapResponse(
        video_id=video_id,
        bucket_size=settings.BUCKET_SIZE,
        total_buckets=len(buckets),
        buckets=buckets,
    )


async def get_highlights(
    db: AsyncIOMotorDatabase,
    video_id: str,
    limit: int,
) -> HighlightsResponse:
    """Return the top N most-engaging segments for a video.

    Raises NotFoundError if no heatmap data exists.
    """
    rows = await repo.get_top_buckets(db, video_id, limit)
    if not rows:
        raise NotFoundError("heatmap")

    highlights = [
        BucketItem(
            bucket=r["bucket"],
            score=r["score"],
            label=make_label(r["bucket"], settings.BUCKET_SIZE),
        )
        for r in rows
    ]
    return HighlightsResponse(video_id=video_id, highlights=highlights)

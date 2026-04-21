from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


async def upsert_bucket(
    db: AsyncIOMotorDatabase,
    video_id: str,
    bucket: int,
    weight: int,
) -> None:
    """Upsert a heatmap bucket document in MongoDB.

    Each document represents one 5-second segment of a video.
    On conflict (same videoId + bucket) the score is incremented and
    ``last_updated`` is refreshed.

    Schema:
        videoId      str    — UUID of the video
        bucket       int    — start second of the 5-second window (e.g. 140)
        score        int    — cumulative weighted engagement score
        last_updated str    — ISO-8601 timestamp of the last write
    """
    now = datetime.now(timezone.utc).isoformat()
    await db.heatmap_buckets.update_one(
        {"videoId": video_id, "bucket": bucket},
        {
            "$inc": {"score": weight},
            "$set": {"last_updated": now},
            "$setOnInsert": {"videoId": video_id, "bucket": bucket},
        },
        upsert=True,
    )

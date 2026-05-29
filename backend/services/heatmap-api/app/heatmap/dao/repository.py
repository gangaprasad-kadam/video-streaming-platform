from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase


async def get_all_buckets(db: AsyncIOMotorDatabase, video_id: str) -> list[dict]:
    """Return all bucket documents for a video, sorted by bucket index."""
    cursor = db.heatmap_buckets.find(
        {"videoId": video_id},
        {"_id": 0, "bucket": 1, "score": 1},
    ).sort("bucket", 1)
    return await cursor.to_list(length=None)


async def get_top_buckets(
    db: AsyncIOMotorDatabase,
    video_id: str,
    limit: int = 5,
) -> list[dict]:
    """Return the top N buckets ranked by score (highest first)."""
    cursor = db.heatmap_buckets.find(
        {"videoId": video_id},
        {"_id": 0, "bucket": 1, "score": 1},
    ).sort("score", -1).limit(limit)
    return await cursor.to_list(length=limit)

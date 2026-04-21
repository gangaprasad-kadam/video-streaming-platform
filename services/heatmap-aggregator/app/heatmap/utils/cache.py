from redis.asyncio import Redis

from app.config import settings
from app.heatmap.utils.schemas import ACTION_WEIGHTS, InteractionEvent


def _bucket(video_ts: float) -> int:
    """Map a video timestamp (seconds) to the start of its 5-second bucket."""
    return int(video_ts // settings.BUCKET_SIZE) * settings.BUCKET_SIZE


async def record_event(redis: Redis, event: InteractionEvent) -> int:
    """Increment heatmap counters in Redis for a single interaction event.

    Writes to two keys per event:
    - ``heatmap:{videoId}:total:{bucket}``  — all-time cumulative score (no TTL)
    - ``heatmap:{videoId}:live:{bucket}``   — recent activity (LIVE_TTL seconds TTL)

    Returns:
        The bucket index (start second) where the event was recorded.
    """
    bucket = _bucket(event.videoTs)
    weight = ACTION_WEIGHTS.get(event.action, 1)

    total_key = f"heatmap:{event.videoId}:total:{bucket}"
    live_key = f"heatmap:{event.videoId}:live:{bucket}"

    async with redis.pipeline(transaction=False) as pipe:
        pipe.incrby(total_key, weight)
        pipe.incrby(live_key, weight)
        pipe.expire(live_key, settings.LIVE_TTL)
        await pipe.execute()

    return bucket

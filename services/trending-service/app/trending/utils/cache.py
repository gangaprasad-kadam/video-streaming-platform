from redis.asyncio import Redis

from app.config import settings

# Score weights for each interaction action.
# Higher weight = stronger signal of viewer interest.
# SKIP is negative — it penalises videos that viewers abandon early.
ACTION_SCORES: dict[str, float] = {
    "PLAY": 1.0,
    "WATCH_COMPLETE": 10.0,
    "REWIND": 3.0,
    "SEEK": 1.0,
    "PAUSE": 0.5,
    "SKIP": -0.5,
}


async def increment_score(redis: Redis, video_id: str, action: str) -> None:
    """Increment the trending score for a video by the action's weight.

    Args:
        redis: Active Redis client.
        video_id: UUID string of the video.
        action: Interaction action name (PLAY, WATCH_COMPLETE, etc.).
    """
    delta = ACTION_SCORES.get(action, 0.0)
    if delta != 0.0:
        await redis.zincrby(settings.TRENDING_KEY, delta, video_id)


async def get_top_videos(redis: Redis, limit: int) -> list[tuple[str, float]]:
    """Fetch the top ``limit`` videos from the trending sorted set.

    Args:
        redis: Active Redis client.
        limit: Maximum number of results to return.

    Returns:
        List of ``(video_id, score)`` tuples ordered by score descending.
    """
    results = await redis.zrevrange(settings.TRENDING_KEY, 0, limit - 1, withscores=True)
    return [(vid, score) for vid, score in results]


async def apply_score_decay(redis: Redis) -> int:
    """Apply the hourly score decay multiplier to all trending scores.

    Multiplies every score by ``settings.SCORE_DECAY_FACTOR`` (default 0.9).
    Scores that drop below 0.01 are removed to keep the set clean.

    Args:
        redis: Active Redis client.

    Returns:
        Number of entries that were removed due to falling below threshold.
    """
    members = await redis.zrange(settings.TRENDING_KEY, 0, -1, withscores=True)
    pipe = redis.pipeline()
    removed = 0
    for video_id, score in members:
        new_score = score * settings.SCORE_DECAY_FACTOR
        if new_score < 0.01:
            pipe.zrem(settings.TRENDING_KEY, video_id)
            removed += 1
        else:
            pipe.zadd(settings.TRENDING_KEY, {video_id: new_score})
    await pipe.execute()
    return removed

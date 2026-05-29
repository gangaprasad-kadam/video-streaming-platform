import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

from app.heatmap.dao import repository as repo
from app.heatmap.utils.cache import record_event
from app.heatmap.utils.schemas import ACTION_WEIGHTS, InteractionEvent

logger = logging.getLogger(__name__)


async def handle_interaction(
    db: AsyncIOMotorDatabase,
    redis: Redis,
    event: InteractionEvent,
) -> None:
    """Process a single viewer interaction event.

    1. Writes weighted score to Redis (total + live buckets).
    2. Persists the same increment to MongoDB for long-term storage.

    Skips actions with no defined weight (unknown action types).
    """
    if event.action not in ACTION_WEIGHTS:
        logger.warning("Unknown action '%s' — skipping", event.action)
        return

    weight = ACTION_WEIGHTS[event.action]
    bucket = await record_event(redis, event)
    await repo.upsert_bucket(db, event.videoId, bucket, weight)

    logger.info(
        "Recorded %s (w=%d) for video=%s bucket=%ds",
        event.action, weight, event.videoId, bucket,
    )

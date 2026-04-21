import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.database import AsyncSessionFactory
from app.redis_client import get_redis
from app.trending.utils.schemas import InteractionEvent
from app.trending.utils import service as trending_service

logger = logging.getLogger(__name__)


async def run_consumer() -> None:
    """Long-running Kafka consumer loop for viewer interaction events.

    Consumes from ``viewer-interaction-events`` topic and delegates to
    ``trending_service.handle_interaction`` for scoring and DB writes.
    Runs until the asyncio task is cancelled (application shutdown).
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_CONSUME,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )

    await consumer.start()
    logger.info("Trending consumer started — listening on '%s'", settings.KAFKA_TOPIC_CONSUME)

    try:
        async for msg in consumer:
            try:
                payload = json.loads(msg.value.decode("utf-8"))
                event = InteractionEvent(**payload)
                redis = get_redis()
                async with AsyncSessionFactory() as db:
                    await trending_service.handle_interaction(db, redis, event)
                logger.info(
                    "[%s] Processed %s event for video %s",
                    event.userId,
                    event.action,
                    event.videoId,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Error processing interaction event: %s", exc)
    finally:
        await consumer.stop()
        logger.info("Trending consumer stopped")

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.mongo_client import get_db
from app.redis_client import get_redis
from app.heatmap.utils.schemas import InteractionEvent
from app.heatmap.utils import service as heatmap_service

logger = logging.getLogger(__name__)


async def run_consumer() -> None:
    """Long-running Kafka consumer loop for viewer interaction events.

    Consumes from ``viewer-interaction-events``, maps each event to a
    5-second bucket, and writes weighted scores to Redis + MongoDB.
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
    logger.info(
        "Heatmap consumer started — listening on '%s'", settings.KAFKA_TOPIC_CONSUME
    )

    try:
        async for msg in consumer:
            try:
                payload = json.loads(msg.value.decode("utf-8"))
                event = InteractionEvent(**payload)
                redis = get_redis()
                db = get_db()
                await heatmap_service.handle_interaction(db, redis, event)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error processing heatmap event: %s", exc)
    finally:
        await consumer.stop()
        logger.info("Heatmap consumer stopped")

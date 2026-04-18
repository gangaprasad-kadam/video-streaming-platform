import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.database import AsyncSessionFactory
from app.redis_client import get_redis
from app.summary.utils.service import process_video

logger = logging.getLogger(__name__)


async def run_consumer() -> None:
    """Start the Kafka consumer and process ``video.processed`` events.

    Runs indefinitely until cancelled (e.g. on application shutdown).
    Each message is dispatched to ``_handle_event`` for processing.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_CONSUME,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    await consumer.start()
    logger.info(f"Consumer started — listening on '{settings.KAFKA_TOPIC_CONSUME}'")

    try:
        async for msg in consumer:
            await _handle_event(msg.value)
    except asyncio.CancelledError:
        logger.info("Consumer cancelled — shutting down")
    finally:
        await consumer.stop()
        logger.info("Consumer stopped")


async def _handle_event(event: dict) -> None:
    """Process a single ``video.processed`` Kafka event.

    Extracts ``videoId`` and ``hlsPath`` from the event payload, then
    triggers the full AI summarization pipeline. Malformed events are
    logged and skipped. Failures are caught and logged without re-raising
    so the consumer loop continues.

    Args:
        event: Decoded Kafka message value containing ``videoId`` and ``hlsPath``.
    """
    video_id = event.get("videoId")
    hls_path = event.get("hlsPath")

    if not video_id or not hls_path:
        logger.warning(f"Malformed event — skipping: {event}")
        return

    logger.info(f"[{video_id}] Processing for AI summarization")

    try:
        async with AsyncSessionFactory() as db:
            redis = get_redis()
            await process_video(db, redis, video_id, hls_path)
        logger.info(f"[{video_id}] Summarization complete")
    except Exception as exc:
        logger.exception(f"[{video_id}] Summarization failed: {exc}")

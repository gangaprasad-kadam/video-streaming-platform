import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.thumbnail.dao.mongo_dao import log_processing_event
from app.thumbnail.utils.ffmpeg import extract_thumbnail
from app.thumbnail.utils.http_client import update_video_thumbnail

logger = logging.getLogger(__name__)


async def run_consumer(stop_event: asyncio.Event) -> None:
    """Start the Kafka consumer and process incoming ``video.uploaded`` events.

    Consumes messages from the configured topic until ``stop_event`` is set.
    Each message is dispatched to ``_handle_event`` for thumbnail extraction.

    Args:
        stop_event: When set, causes the consumer loop to exit cleanly after
            the current message is processed.
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
            if stop_event.is_set():
                break
            await _handle_event(msg.value)
    finally:
        await consumer.stop()


async def _handle_event(event: dict) -> None:
    """Process a single ``video.uploaded`` Kafka event by extracting a thumbnail.

    Validates the payload, runs thumbnail extraction via ffmpeg, notifies the
    video-service of the result, and logs each stage to MongoDB. Errors are
    caught and logged without re-raising so the consumer keeps running.

    Args:
        event: Deserialized Kafka message payload. Expected keys: ``videoId``
            and ``filePath``.
    """
    video_id = event.get("videoId")
    file_path = event.get("filePath")

    if not video_id or not file_path:
        logger.warning(f"Malformed event — skipping: {event}")
        return

    logger.info(f"[{video_id}] Thumbnail extraction started")
    await log_processing_event(video_id, "thumbnail_started", {"file_path": file_path})

    try:
        thumbnail_path = await extract_thumbnail(video_id, file_path)
        await update_video_thumbnail(video_id, thumbnail_path)
        await log_processing_event(video_id, "thumbnail_completed", {"thumbnail_path": thumbnail_path})
        logger.info(f"[{video_id}] Thumbnail saved: {thumbnail_path}")

    except Exception as exc:
        logger.exception(f"[{video_id}] Thumbnail extraction failed: {exc}")
        await log_processing_event(video_id, "thumbnail_failed", {"error": str(exc)})

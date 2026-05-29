import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.encoding.dao.mongo_dao import log_processing_event
from app.encoding.utils.ffmpeg import transcode_to_hls
from app.encoding.utils.http_client import update_video_status
from app.encoding.utils.kafka_producer import publish_processed, start_producer, stop_producer

logger = logging.getLogger(__name__)


async def run_consumer(stop_event: asyncio.Event) -> None:
    """Start the Kafka consumer and process incoming ``video.uploaded`` events.

    Initializes the Kafka producer, then consumes messages from the configured
    topic until ``stop_event`` is set. Each message is dispatched to
    ``_handle_event`` for encoding.

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

    await start_producer()
    await consumer.start()
    logger.info(f"Consumer started — listening on '{settings.KAFKA_TOPIC_CONSUME}'")

    try:
        async for msg in consumer:
            if stop_event.is_set():
                break
            await _handle_event(msg.value)
    finally:
        await consumer.stop()
        await stop_producer()


async def _handle_event(event: dict) -> None:
    """Process a single ``video.uploaded`` Kafka event end-to-end.

    Validates the payload, triggers HLS transcoding, updates the video-service
    with the result, logs every stage to MongoDB, and publishes a
    ``video.processed`` event on success. Marks the video as ``failed`` if any
    step raises an exception.

    Args:
        event: Deserialized Kafka message payload. Expected keys: ``videoId``,
            ``filePath``, and optionally ``mimeType``.
    """
    video_id = event.get("videoId")
    file_path = event.get("filePath")
    mime_type = event.get("mimeType", "video/mp4")

    if not video_id or not file_path:
        logger.warning(f"Malformed event — skipping: {event}")
        return

    logger.info(f"[{video_id}] Encoding started: {file_path}")
    await update_video_status(video_id, status="processing")
    await log_processing_event(video_id, "encoding_started", {"file_path": file_path})

    try:
        result = await transcode_to_hls(video_id, file_path)

        await update_video_status(
            video_id,
            status="ready",
            hls_path=result["hls_path"],
            duration=result["duration"],
        )
        await log_processing_event(video_id, "encoding_completed", result)

        await publish_processed(video_id, result["hls_path"], result["duration"])
        logger.info(f"[{video_id}] Encoding completed successfully")

    except Exception as exc:
        logger.exception(f"[{video_id}] Encoding failed: {exc}")
        await update_video_status(video_id, status="failed")
        await log_processing_event(video_id, "encoding_failed", {"error": str(exc)})

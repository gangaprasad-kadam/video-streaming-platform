import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)
_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    """Initialize and start the global Kafka producer instance."""
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await _producer.start()
    logger.info("Kafka producer started")


async def stop_producer() -> None:
    """Flush pending messages and shut down the global Kafka producer."""
    if _producer:
        await _producer.stop()
        logger.info("Kafka producer stopped")


async def publish_processed(
    video_id: str,
    hls_path: str | None,
    duration: float | None,
) -> None:
    """Publish a ``video.processed`` event to Kafka.

    Args:
        video_id: ID of the video that finished encoding.
        hls_path: Absolute path to the HLS manifest file, or ``None`` if
            transcoding did not produce one.
        duration: Video length in seconds, or ``None`` if unknown.

    Raises:
        RuntimeError: If the producer has not been started via
            ``start_producer`` before this call.
    """
    if _producer is None:
        raise RuntimeError("Kafka producer not started")
    await _producer.send_and_wait(
        settings.KAFKA_TOPIC_PRODUCE,
        key=video_id.encode(),
        value={
            "videoId": video_id,
            "hlsPath": hls_path,
            "duration": duration,
            "processedAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    logger.info(f"[{video_id}] Published to '{settings.KAFKA_TOPIC_PRODUCE}'")

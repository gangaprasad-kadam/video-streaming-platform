import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)
_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await _producer.start()
    logger.info("Kafka producer started")


async def stop_producer() -> None:
    if _producer:
        await _producer.stop()
        logger.info("Kafka producer stopped")


async def publish_processed(
    video_id: str,
    hls_path: str | None,
    duration: float | None,
) -> None:
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

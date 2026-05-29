import json
import logging

from aiokafka import AIOKafkaProducer
from redis.asyncio import Redis

from app.config import settings
from app.events.utils.cache import check_rate_limit
from app.events.utils.schemas import InteractionEventAccepted, InteractionEventRequest

logger = logging.getLogger(__name__)


async def ingest_event(
    producer: AIOKafkaProducer,
    redis: Redis,
    event: InteractionEventRequest,
) -> InteractionEventAccepted:
    """Validate rate limit then publish the interaction event to Kafka.

    Raises:
        TooManyRequestsError: when the user exceeds RATE_LIMIT_PER_MINUTE.
    """
    from app.exceptions import TooManyRequestsError

    allowed = await check_rate_limit(redis, event.userId)
    if not allowed:
        raise TooManyRequestsError(user_id=event.userId)

    payload = json.dumps(event.model_dump()).encode("utf-8")
    key = event.videoId.encode("utf-8")

    await producer.send_and_wait(settings.KAFKA_TOPIC, value=payload, key=key)
    logger.info("Ingested %s event for video %s by user %s", event.action, event.videoId, event.userId)

    return InteractionEventAccepted(action=event.action, videoId=event.videoId)

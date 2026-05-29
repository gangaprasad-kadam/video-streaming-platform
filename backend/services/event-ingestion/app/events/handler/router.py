from fastapi import APIRouter, Depends, status
from aiokafka import AIOKafkaProducer
from redis.asyncio import Redis

from app.events.utils import service as event_service
from app.events.utils.schemas import InteractionEventAccepted, InteractionEventRequest
from app.kafka_producer import get_producer
from app.redis_client import get_redis

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/interaction",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InteractionEventAccepted,
)
async def ingest_interaction(
    event: InteractionEventRequest,
    producer: AIOKafkaProducer = Depends(get_producer),
    redis: Redis = Depends(get_redis),
):
    """Accept a viewer interaction event and publish it to Kafka asynchronously.

    Returns 202 immediately — the event is fire-and-forget from the client's
    perspective. The trending-service consumer processes it downstream.

    Rate limited to 60 events per user per minute.
    """
    return await event_service.ingest_event(producer, redis, event)

import json

from aiokafka import AIOKafkaProducer

from app.config import settings

_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    """Initialise and start the global AIOKafka producer.

    Must be called once during application startup (e.g., in the lifespan hook)
    before any calls to :func:`publish`.
    """
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await _producer.start()


async def stop_producer() -> None:
    """Gracefully shut down the global Kafka producer.

    Safe to call even if the producer was never started.
    """
    if _producer:
        await _producer.stop()


async def publish(topic: str, key: str, value: dict) -> None:
    """Send a JSON message to a Kafka topic and wait for acknowledgement.

    Args:
        topic: Kafka topic name (e.g., ``"video.uploaded"``).
        key: Partition key string; encoded to bytes internally.
        value: Message payload; serialised to JSON automatically.

    Raises:
        RuntimeError: If :func:`start_producer` has not been called.
    """
    if _producer is None:
        raise RuntimeError("Kafka producer not started")
    await _producer.send_and_wait(topic, key=key.encode(), value=value)


def get_producer() -> AIOKafkaProducer:
    """Return the running Kafka producer instance.

    Returns:
        The global AIOKafkaProducer.

    Raises:
        RuntimeError: If :func:`start_producer` has not been called.
    """
    if _producer is None:
        raise RuntimeError("Kafka producer not started")
    return _producer

from aiokafka import AIOKafkaProducer

_producer: AIOKafkaProducer | None = None


async def connect_producer() -> None:
    global _producer
    from app.config import settings
    _producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    await _producer.start()


async def close_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


def get_producer() -> AIOKafkaProducer:
    if _producer is None:
        raise RuntimeError("Kafka producer not initialised")
    return _producer

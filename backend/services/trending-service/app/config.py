from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a ``.env`` file.

    Attributes:
        DATABASE_URL: Async PostgreSQL connection string for asyncpg.
        REDIS_URL: Redis connection URL (DB 4 for trending).
        KAFKA_BOOTSTRAP_SERVERS: Comma-separated Kafka broker addresses.
        KAFKA_GROUP_ID: Kafka consumer group ID.
        KAFKA_TOPIC_CONSUME: Topic to consume viewer interaction events from.
        TRENDING_KEY: Redis sorted set key for trending scores.
        TRENDING_LIMIT: Default number of results for trending endpoint.
        SCORE_DECAY_FACTOR: Multiplier applied to all scores every hour.
        DEBUG: Enables SQLAlchemy query echo when ``True``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://user:password@postgres:5432/videodb"
    REDIS_URL: str = "redis://redis:6379/4"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_GROUP_ID: str = "trending-service"
    KAFKA_TOPIC_CONSUME: str = "viewer-interaction-events"
    TRENDING_KEY: str = "trending:scores"
    TRENDING_LIMIT: int = 20
    SCORE_DECAY_FACTOR: float = 0.9
    VIDEO_SERVICE_URL: str = "http://video-service:8002"
    DEBUG: bool = False


settings = Settings()

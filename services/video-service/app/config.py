from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a ``.env`` file.

    Attributes:
        DATABASE_URL: Async PostgreSQL connection string for asyncpg.
        REDIS_URL: Redis connection URL.
        KAFKA_BOOTSTRAP_SERVERS: Comma-separated Kafka broker addresses.
        MEDIA_ROOT: Filesystem root where uploaded and processed media is stored.
        DEBUG: Enables SQLAlchemy query echo when ``True``.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://user:password@postgres:5432/videodb"
    REDIS_URL: str = "redis://redis:6379/0"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    MEDIA_ROOT: str = "/media"
    DEBUG: bool = False


settings = Settings()

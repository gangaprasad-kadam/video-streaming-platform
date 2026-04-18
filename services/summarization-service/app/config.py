from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://user:password@postgres:5432/videoplatform"
    REDIS_URL: str = "redis://redis:6379/3"

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_GROUP_ID: str = "summarization-service"
    KAFKA_TOPIC_CONSUME: str = "video.processed"

    WHISPER_MODEL: str = "base"
    BART_MODEL: str = "sshleifer/distilbart-cnn-12-6"
    SUMMARY_CACHE_TTL: int = 3600  # 1 hour

    DEBUG: bool = False


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str = "redis://redis:6379/5"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC: str = "viewer-interaction-events"

    # Max events per user per minute (Redis rate limiting)
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()

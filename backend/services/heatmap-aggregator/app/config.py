from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str = "redis://redis:6379/6"
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_CONSUME: str = "viewer-interaction-events"
    KAFKA_GROUP_ID: str = "heatmap-aggregator"
    MONGO_URL: str = "mongodb://mongo:27017"
    MONGO_DB: str = "heatmaps"

    # Width of each heatmap bucket in seconds
    BUCKET_SIZE: int = 5
    # TTL for the live (recent) Redis keys in seconds (5 minutes)
    LIVE_TTL: int = 300


settings = Settings()

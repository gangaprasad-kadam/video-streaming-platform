from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_GROUP_ID: str = "thumbnail-worker"
    KAFKA_TOPIC_CONSUME: str = "video.uploaded"

    VIDEO_SERVICE_URL: str = "http://video-service:8002"

    MEDIA_ROOT: str = "/media"

    MONGO_URL: str = "mongodb://mongo:27017"
    MONGO_DB: str = "platform"


settings = Settings()

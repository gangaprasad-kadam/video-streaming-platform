from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str = "redis://redis:6379/2"
    MEDIA_ROOT: str = "/media"
    MANIFEST_CACHE_TTL: int = 300  # 5 minutes
    VIDEO_SERVICE_URL: str = "http://video-service:8002"


settings = Settings()

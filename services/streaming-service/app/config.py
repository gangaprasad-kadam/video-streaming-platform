from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://user:password@postgres:5432/videoplatform"
    REDIS_URL: str = "redis://redis:6379/2"
    MEDIA_ROOT: str = "/media"
    MANIFEST_CACHE_TTL: int = 300  # 5 minutes
    DEBUG: bool = False


settings = Settings()

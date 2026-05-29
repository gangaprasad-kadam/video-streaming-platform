from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://user:password@postgres:5432/userdb"
    REDIS_URL: str = "redis://redis:6379/0"
    SESSION_TTL: int = 86400  # 24 hours in seconds
    DEBUG: bool = False


settings = Settings()

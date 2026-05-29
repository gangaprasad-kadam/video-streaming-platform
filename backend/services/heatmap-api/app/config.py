from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str = "redis://redis:6379/6"
    MONGO_URL: str = "mongodb://mongo:27017"
    MONGO_DB: str = "heatmaps"
    BUCKET_SIZE: int = 5


settings = Settings()

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_mongo() -> None:
    global _client, _db
    from app.config import settings
    _client = AsyncIOMotorClient(settings.MONGO_URL)
    _db = _client[settings.MONGO_DB]


async def close_mongo() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not initialised")
    return _db

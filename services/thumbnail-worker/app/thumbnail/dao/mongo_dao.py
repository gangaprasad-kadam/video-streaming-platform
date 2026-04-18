import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

logger = logging.getLogger(__name__)
_client: AsyncIOMotorClient | None = None


def _get_collection():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URL)
    return _client[settings.MONGO_DB]["processing_logs"]


async def log_processing_event(video_id: str, event: str, details: dict) -> None:
    """Persist a processing log entry to MongoDB."""
    try:
        await _get_collection().insert_one({
            "videoId": video_id,
            "event": event,
            "details": details,
            "worker": "thumbnail-worker",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.warning(f"MongoDB log failed for [{video_id}] {event}: {exc}")

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

logger = logging.getLogger(__name__)
_client: AsyncIOMotorClient | None = None


def _get_collection():
    """Return the MongoDB collection used for encoding processing logs.

    Lazily initializes the Motor client on the first call and reuses it on
    subsequent calls.

    Returns:
        An ``AsyncIOMotorCollection`` for the ``processing_logs`` collection.
    """
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URL)
    return _client[settings.MONGO_DB]["processing_logs"]


async def log_processing_event(video_id: str, event: str, details: dict) -> None:
    """Insert an encoding processing log entry into MongoDB.

    Errors from MongoDB are caught and logged as warnings so that logging
    failures never interrupt the main encoding pipeline.

    Args:
        video_id: ID of the video this log entry belongs to.
        event: Short event name, e.g. ``"encoding_started"`` or
            ``"encoding_failed"``.
        details: Arbitrary dict with event-specific context such as file paths
            or error messages.
    """
    try:
        await _get_collection().insert_one({
            "videoId": video_id,
            "event": event,
            "details": details,
            "worker": "encoding-worker",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.warning(f"MongoDB log failed for [{video_id}] {event}: {exc}")

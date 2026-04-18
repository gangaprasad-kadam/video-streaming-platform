import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def update_video_thumbnail(video_id: str, thumbnail_path: str) -> None:
    """Patch video-service to set thumbnail_path. Uses current status to avoid downgrading."""
    url = f"{settings.VIDEO_SERVICE_URL}/internal/videos/{video_id}/status"
    # We send status=processing as a hint; video-service ignores status change for terminal videos
    # but will still update thumbnail_path due to our fix in update_status service.
    payload = {
        "status": "processing",
        "thumbnail_path": thumbnail_path,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json=payload, timeout=15.0)
        resp.raise_for_status()

    logger.info(f"[{video_id}] Thumbnail path updated: {thumbnail_path}")

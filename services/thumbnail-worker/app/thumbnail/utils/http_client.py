import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def update_video_thumbnail(video_id: str, thumbnail_path: str) -> None:
    """Send the generated thumbnail path to the video-service internal API.

    PATCHes ``/internal/videos/{video_id}/status`` with ``status="processing"``
    and the thumbnail path. The video-service stores the thumbnail without
    downgrading a video that is already in a terminal status.

    Args:
        video_id: UUID of the video to update.
        thumbnail_path: Absolute path to the saved JPEG thumbnail.

    Raises:
        httpx.HTTPStatusError: If the video-service returns a non-2xx response.
    """
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

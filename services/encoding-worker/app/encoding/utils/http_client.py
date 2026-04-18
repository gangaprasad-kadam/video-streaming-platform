import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def update_video_status(
    video_id: str,
    status: str,
    hls_path: str | None = None,
    thumbnail_path: str | None = None,
    duration: float | None = None,
) -> None:
    """Call video-service internal PATCH to update video status and metadata."""
    url = f"{settings.VIDEO_SERVICE_URL}/internal/videos/{video_id}/status"
    payload: dict = {"status": status}
    if hls_path is not None:
        payload["hls_path"] = hls_path
    if thumbnail_path is not None:
        payload["thumbnail_path"] = thumbnail_path
    if duration is not None:
        payload["duration"] = duration

    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json=payload, timeout=15.0)
        resp.raise_for_status()

    logger.info(f"[{video_id}] Status updated → {status}")

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
    """Update a video's status and optional metadata via the video-service internal API.

    Sends a PATCH to ``/internal/videos/{video_id}/status``. Only fields with
    non-``None`` values are included in the request body.

    Args:
        video_id: UUID of the video to update.
        status: New lifecycle status, e.g. ``"processing"``, ``"ready"``, or
            ``"failed"``.
        hls_path: Absolute path to the HLS manifest file, if available.
        thumbnail_path: Absolute path to the generated thumbnail image, if available.
        duration: Video length in seconds, if known.

    Raises:
        httpx.HTTPStatusError: If the video-service returns a non-2xx response.
    """
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

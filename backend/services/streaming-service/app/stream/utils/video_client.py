"""HTTP client for fetching video stream info from video-service.

Provides strict API isolation: streaming-service never queries video-service's DB directly.
"""
import httpx

from app.config import settings

_TIMEOUT = 5.0  # seconds


async def get_stream_info(video_id: str) -> dict | None:
    """Fetch stream info (id, status, hls_path) for a ready video from video-service.

    Args:
        video_id: UUID string of the target video.

    Returns:
        Dict with ``id``, ``status``, and ``hls_path`` fields, or ``None`` if the
        video is not found, not ready, or video-service is unreachable.
    """
    url = f"{settings.VIDEO_SERVICE_URL}/internal/videos/{video_id}/stream-info"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return None
        return resp.json().get("data")
    except Exception:
        return None

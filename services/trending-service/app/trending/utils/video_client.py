"""HTTP client for calling video-service internal endpoints.

Trending-service uses this instead of querying the videos table directly,
following strict service isolation — each service owns its own data.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def get_videos_by_ids(video_ids: list[str]) -> list[dict]:
    """Fetch ready videos from video-service by their IDs.

    Calls ``GET /internal/videos/batch?ids=id1,id2,...``.

    Args:
        video_ids: List of video UUID strings to look up.

    Returns:
        List of VideoResponse dicts. Videos that are not ``ready`` or
        do not exist are silently excluded by video-service.
    """
    if not video_ids:
        return []
    ids_param = ",".join(video_ids)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.VIDEO_SERVICE_URL}/internal/videos/batch",
                params={"ids": ids_param},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as exc:
        logger.error("video-service batch fetch failed: %s", exc)
        return []


async def get_videos_by_creators(
    creator_ids: list[str], exclude_ids: list[str], limit: int = 40
) -> list[dict]:
    """Fetch ready videos by creator from video-service, excluding given IDs.

    Calls ``GET /internal/videos/by-creators``.

    Args:
        creator_ids: List of creator UUID strings.
        exclude_ids: Video UUIDs to exclude (already watched or trending picks).
        limit: Maximum number of videos to return.

    Returns:
        List of VideoResponse dicts.
    """
    if not creator_ids:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.VIDEO_SERVICE_URL}/internal/videos/by-creators",
                params={
                    "creator_ids": ",".join(creator_ids),
                    "exclude_ids": ",".join(exclude_ids),
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as exc:
        logger.error("video-service by-creators fetch failed: %s", exc)
        return []

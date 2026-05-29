from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.trending.dao import repository as repo
from app.trending.utils import video_client
from app.trending.utils.cache import get_top_videos, increment_score
from app.trending.utils.schemas import (
    InteractionEvent,
    RecommendationItem,
    RecommendationsResponse,
    TrendingResponse,
    TrendingVideoItem,
)


async def handle_interaction(
    db: AsyncSession, redis: Redis, event: InteractionEvent
) -> None:
    """Process one viewer interaction event.

    Increments the trending score in Redis. On PLAY events, also upserts
    the watch_history table so recommendations can filter already-seen videos.

    Args:
        db: Active async database session.
        redis: Active Redis client.
        event: Parsed interaction event from Kafka.
    """
    await increment_score(redis, event.videoId, event.action)

    if event.action == "PLAY" and event.creatorId:
        await repo.upsert_watch_history(db, event.userId, event.videoId, event.creatorId)


async def get_trending(
    db: AsyncSession, redis: Redis, limit: int
) -> TrendingResponse:
    """Return the top ``limit`` trending videos enriched with metadata from video-service.

    Args:
        db: Unused — kept for interface consistency with the dependency injection pattern.
        redis: Active Redis client.
        limit: Maximum number of results to return.

    Returns:
        TrendingResponse with ranked video list.
    """
    top = await get_top_videos(redis, limit)
    if not top:
        return TrendingResponse(videos=[], total=0)

    video_ids = [vid for vid, _ in top]
    score_map = {vid: score for vid, score in top}

    # Call video-service via HTTP — strict service isolation
    video_list = await video_client.get_videos_by_ids(video_ids)
    video_map = {v["id"]: v for v in video_list}

    items: list[TrendingVideoItem] = []
    rank = 1
    for video_id in video_ids:
        video = video_map.get(video_id)
        if not video:
            continue  # not ready or deleted — skip
        items.append(
            TrendingVideoItem(
                video_id=video_id,
                title=video["title"],
                creator_id=video["creator_id"],
                thumbnail_path=video.get("thumbnail_path"),
                duration=video.get("duration"),
                score=score_map[video_id],
                rank=rank,
            )
        )
        rank += 1

    return TrendingResponse(videos=items, total=len(items))


async def get_recommendations(
    db: AsyncSession, redis: Redis, user_id: str, limit: int
) -> RecommendationsResponse:
    """Build a hybrid recommendation list: 60% trending + 40% creator-based.

    Algorithm:
    1. Fetch top 50 trending video IDs from Redis.
    2. Fetch user's watch history from DB (this is trending-service's own data).
    3. Remove watched videos from trending candidates.
    4. Extract distinct creator IDs from the user's watch history.
    5. Call video-service for creator-based videos (HTTP).
    6. Merge: trending_slots = ceil(60% of limit), creator_slots = floor(40% of limit).

    Args:
        db: Active async database session (used for watch_history — trending-service owns this).
        redis: Active Redis client.
        user_id: UUID string of the requesting user.
        limit: Total number of recommendations to return.

    Returns:
        RecommendationsResponse with blended video list.
    """
    trending_slots = max(1, round(limit * 0.6))
    creator_slots = limit - trending_slots

    # Step 1: Get top 50 trending (fetch extra to have enough after filtering)
    raw_trending = await get_top_videos(redis, 50)
    trending_ids = [vid for vid, _ in raw_trending]

    # Step 2: User's watch history — this IS trending-service's own data
    history = await repo.get_watch_history(db, user_id)
    watched_ids = {str(h.video_id) for h in history}
    creator_ids = list({str(h.creator_id) for h in history})

    # Step 3: Filter trending (remove watched)
    unwatched_trending_ids = [vid for vid in trending_ids if vid not in watched_ids]

    # Step 4: Enrich trending candidates via video-service HTTP call
    trending_candidates = await video_client.get_videos_by_ids(
        unwatched_trending_ids[:trending_slots]
    )
    trending_map = {v["id"]: v for v in trending_candidates}

    trending_items: list[RecommendationItem] = []
    for vid_id in unwatched_trending_ids:
        if len(trending_items) >= trending_slots:
            break
        video = trending_map.get(vid_id)
        if not video:
            continue
        trending_items.append(
            RecommendationItem(
                video_id=vid_id,
                title=video["title"],
                creator_id=video["creator_id"],
                thumbnail_path=video.get("thumbnail_path"),
                duration=video.get("duration"),
                reason="trending",
            )
        )

    # Step 5: Creator-based slice via video-service HTTP call
    all_excluded = list(watched_ids | {v.video_id for v in trending_items})
    creator_video_list = await video_client.get_videos_by_creators(
        creator_ids, all_excluded, limit=creator_slots
    )

    creator_items: list[RecommendationItem] = [
        RecommendationItem(
            video_id=v["id"],
            title=v["title"],
            creator_id=v["creator_id"],
            thumbnail_path=v.get("thumbnail_path"),
            duration=v.get("duration"),
            reason="creator",
        )
        for v in creator_video_list[:creator_slots]
    ]

    merged = trending_items + creator_items
    return RecommendationsResponse(user_id=user_id, videos=merged, total=len(merged))

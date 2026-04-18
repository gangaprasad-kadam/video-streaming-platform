import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import SummaryNotFoundError
from app.summary.dao import repository as repo
from app.summary.utils.bart_utils import summarize
from app.summary.utils.cache import cache_summary, get_cached_summary
from app.summary.utils.schemas import KeyMoment, SummaryResponse
from app.summary.utils.whisper_utils import (
    cleanup_audio,
    extract_audio,
    extract_key_moments,
    transcribe,
)

logger = logging.getLogger(__name__)


async def get_summary(db: AsyncSession, redis: Redis, video_id: str) -> SummaryResponse:
    """Cache-aside: Redis (1h) → PostgreSQL → 404."""
    cached = await get_cached_summary(redis, video_id)
    if cached:
        return SummaryResponse(**cached)

    record = await repo.get_by_video_id(db, video_id)
    if not record:
        raise SummaryNotFoundError(video_id)

    response = SummaryResponse(
        video_id=str(record.video_id),
        transcript=record.transcript,
        summary=record.summary,
        key_moments=[KeyMoment(**km) for km in record.key_moments],
        created_at=record.created_at.isoformat(),
    )
    await cache_summary(redis, video_id, response.model_dump())
    return response


async def process_video(
    db: AsyncSession,
    redis: Redis,
    video_id: str,
    hls_path: str,
) -> None:
    """Full pipeline: audio extraction → transcription → summarization → store."""
    # Skip if already processed (idempotent)
    existing = await repo.get_by_video_id(db, video_id)
    if existing:
        logger.info(f"[{video_id}] Summary already exists — skipping")
        return

    audio_path = None
    try:
        logger.info(f"[{video_id}] Extracting audio from {hls_path}")
        audio_path = await extract_audio(video_id, hls_path)

        logger.info(f"[{video_id}] Running Whisper transcription")
        whisper_result = await transcribe(audio_path, settings.WHISPER_MODEL)

        transcript = whisper_result.get("text", "").strip()
        segments = whisper_result.get("segments", [])
        key_moments = extract_key_moments(segments)

        logger.info(f"[{video_id}] Running BART summarization")
        summary_text = await summarize(transcript, settings.BART_MODEL)

        await repo.create_summary(
            db,
            video_id=video_id,
            transcript=transcript,
            summary=summary_text,
            key_moments=key_moments,
        )

        # Prime the cache
        record = await repo.get_by_video_id(db, video_id)
        if record:
            response = SummaryResponse(
                video_id=str(record.video_id),
                transcript=record.transcript,
                summary=record.summary,
                key_moments=[KeyMoment(**km) for km in record.key_moments],
                created_at=record.created_at.isoformat(),
            )
            await cache_summary(redis, video_id, response.model_dump())

    finally:
        if audio_path:
            cleanup_audio(audio_path)

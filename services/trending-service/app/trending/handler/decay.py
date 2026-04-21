import asyncio
import logging

from app.config import settings
from app.redis_client import get_redis
from app.trending.utils.cache import apply_score_decay

logger = logging.getLogger(__name__)

_DECAY_INTERVAL_SECONDS = 3600  # 1 hour


async def run_decay_loop() -> None:
    """Background task that applies score decay every hour.

    Multiplies all trending scores by ``settings.SCORE_DECAY_FACTOR`` (0.9),
    and prunes entries that drop below 0.01 to keep the sorted set clean.
    Runs indefinitely until the asyncio task is cancelled.
    """
    logger.info("Score decay loop started (interval=%ds, factor=%.2f)",
                _DECAY_INTERVAL_SECONDS, settings.SCORE_DECAY_FACTOR)
    while True:
        await asyncio.sleep(_DECAY_INTERVAL_SECONDS)
        try:
            redis = get_redis()
            removed = await apply_score_decay(redis)
            logger.info("Score decay applied — %d low-score entries removed", removed)
        except Exception as exc:  # noqa: BLE001
            logger.error("Score decay error: %s", exc)

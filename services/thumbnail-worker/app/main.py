import asyncio
import logging
import signal

from app.thumbnail.handler.consumer import run_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("thumbnail-worker starting...")
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        logger.info("Shutdown signal received — stopping consumer")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    await run_consumer(stop_event)
    logger.info("thumbnail-worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

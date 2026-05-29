import asyncio
import logging
import signal

from app.encoding.handler.consumer import run_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Start the encoding worker and run until a shutdown signal is received.

    Registers SIGINT and SIGTERM handlers, then delegates to the Kafka consumer
    loop. Blocks until the stop event is set by a signal handler.
    """
    logger.info("encoding-worker starting...")
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        """Set the stop event to trigger a graceful consumer shutdown."""
        logger.info("Shutdown signal received — stopping consumer")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    await run_consumer(stop_event)
    logger.info("encoding-worker stopped")


if __name__ == "__main__":
    asyncio.run(main())

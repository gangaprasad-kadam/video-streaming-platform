import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import close_db, connect_db
from app.redis_client import close_redis, connect_redis
from app.summary.handler.consumer import run_consumer
from app.summary.handler.router import router as summary_router
from shared.exceptions import AppException

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await connect_redis()

    # Start Kafka consumer as background asyncio task
    consumer_task = asyncio.create_task(run_consumer())
    logger.info("Kafka consumer task started")

    yield

    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await close_redis()
    await close_db()


app = FastAPI(title="Summarization Service", lifespan=lifespan, redirect_slashes=False)

app.include_router(summary_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid input",
            "detail": exc.errors(),
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "summarization-service"}

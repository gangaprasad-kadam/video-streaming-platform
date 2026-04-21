import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import close_db, connect_db
from app.redis_client import close_redis, connect_redis
from app.trending.handler.consumer import run_consumer
from app.trending.handler.decay import run_decay_loop
from app.trending.handler.router import router as trending_router
from shared.exceptions import AppException

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown.

    On startup: connects to the database and Redis, then launches the Kafka
    consumer (for scoring) and the score decay loop as background asyncio tasks.
    On shutdown: cancels both background tasks and closes all connections gracefully.

    Args:
        app: The FastAPI application instance.
    """
    await connect_db()
    await connect_redis()

    # Start Kafka consumer and decay loop as background tasks
    consumer_task = asyncio.create_task(run_consumer())
    decay_task = asyncio.create_task(run_decay_loop())

    yield

    consumer_task.cancel()
    decay_task.cancel()
    await asyncio.gather(consumer_task, decay_task, return_exceptions=True)
    await close_redis()
    await close_db()


app = FastAPI(title="Trending Service", lifespan=lifespan, redirect_slashes=False)

app.include_router(trending_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Convert an AppException into a structured JSON error response.

    Args:
        request: The incoming HTTP request.
        exc: The application exception that was raised.

    Returns:
        JSONResponse with the exception's status code and error payload.
    """
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
    """Convert a Pydantic validation error into a structured JSON error response.

    Args:
        request: The incoming HTTP request.
        exc: The validation error raised by FastAPI/Pydantic.

    Returns:
        JSONResponse with status 422 and a list of field-level validation errors.
    """
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
    """Health check endpoint.

    Returns:
        dict with service status and name.
    """
    return {"status": "ok", "service": "trending-service"}

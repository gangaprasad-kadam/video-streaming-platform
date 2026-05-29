from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.redis_client import close_redis, connect_redis
from app.stream.handler.router import router as stream_router
from shared.exceptions import AppException


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown.

    Connects to Redis on startup and disconnects gracefully on shutdown.
    Database access is handled by video-service over HTTP.

    Args:
        app: The FastAPI application instance.
    """
    await connect_redis()
    yield
    await close_redis()


app = FastAPI(title="Streaming Service", lifespan=lifespan, redirect_slashes=False)

app.include_router(stream_router)


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
    return {"status": "ok", "service": "streaming-service"}

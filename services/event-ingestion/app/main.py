import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.kafka_producer import connect_producer, close_producer
from app.redis_client import connect_redis, close_redis
from app.events.handler.router import router as events_router
from shared.exceptions import AppException

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_redis()
    await connect_producer()
    yield
    await close_producer()
    await close_redis()


app = FastAPI(title="Event Ingestion Service", lifespan=lifespan)

app.include_router(events_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_ERROR", "message": "Invalid input", "detail": exc.errors()},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "event-ingestion"}

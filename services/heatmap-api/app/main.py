import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.mongo_client import connect_mongo, close_mongo
from app.redis_client import connect_redis, close_redis
from app.heatmap.handler.router import router as heatmap_router
from shared.exceptions import AppException

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_redis()
    await connect_mongo()
    yield
    await close_mongo()
    await close_redis()


app = FastAPI(title="Heatmap API", lifespan=lifespan, redirect_slashes=False)

app.include_router(heatmap_router)


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
    return {"status": "ok", "service": "heatmap-api"}

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.mongo_client import connect_mongo, close_mongo
from app.redis_client import connect_redis, close_redis
from app.heatmap.handler.consumer import run_consumer

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to Redis and MongoDB, then start the Kafka consumer task."""
    await connect_redis()
    await connect_mongo()
    consumer_task = asyncio.create_task(run_consumer())
    yield
    consumer_task.cancel()
    await asyncio.gather(consumer_task, return_exceptions=True)
    await close_mongo()
    await close_redis()


app = FastAPI(title="Heatmap Aggregator", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "heatmap-aggregator"}

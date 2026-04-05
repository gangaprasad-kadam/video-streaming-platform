# Shared Patterns Reference

All microservices in this project follow the same cross-cutting patterns. This document is the single source of truth — every phase doc references it rather than repeating the same boilerplate.

---

## 1. Layered Architecture (Every Service)

```
Layer 1 — Presentation   app/{domain}/router.py    — HTTP routes, Pydantic validation, Depends()
                         app/{domain}/schemas.py   — Pydantic request/response models
Layer 2 — Business Logic app/{domain}/service.py   — All business logic, orchestration
Layer 3 — Data           app/models.py             — ALL SQLAlchemy ORM models (service-wide)
                         app/{domain}/repository.py — SQLAlchemy queries only, returns domain objects
                         app/{domain}/cache.py      — Redis get/set/expire, returns None on miss
```

No layer may skip another. Service layer calls repository + cache. Router calls service only.
`models.py` lives at the **app/ level** (shared across all domains in the service).
`schemas.py` lives inside each **{domain}/** folder (domain-specific request/response shapes).

---

## 2. Shared Module (`shared/`)

A Python package mounted into every service container. Lives at `services/shared/`.

```
services/shared/
├── __init__.py
├── dependencies.py   ← FastAPI Depends: get_db, get_redis, get_current_user
├── exceptions.py     ← AppException hierarchy
└── schemas.py        ← SuccessResponse[T], ErrorResponse, PagedResponse[T]
```

### `shared/dependencies.py`

```python
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_redis() -> Redis:
    return redis_client

async def get_current_user(
    request: Request,
    redis: Redis = Depends(get_redis)
) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthError("Not authenticated")
    user_id = await redis.get(f"session:{session_id}")
    if not user_id:
        raise AuthError("Session expired")
    await redis.expire(f"session:{session_id}", 86400)   # sliding TTL
    return user_id.decode()
```

### `shared/exceptions.py`

```python
class AppException(Exception):
    def __init__(self, error: str, message: str, status_code: int, detail=None):
        self.error       = error
        self.message     = message
        self.status_code = status_code
        self.detail      = detail

class NotFoundError(AppException):
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource.upper()}_NOT_FOUND",
                         f"{resource} with id '{id}' not found", 404)

class ConflictError(AppException):
    def __init__(self, message: str):
        super().__init__("CONFLICT", message, 409)

class AuthError(AppException):
    def __init__(self, message="Invalid credentials"):
        super().__init__("UNAUTHORIZED", message, 401)

class ForbiddenError(AppException):
    def __init__(self, message="Access denied"):
        super().__init__("FORBIDDEN", message, 403)

class RateLimitError(AppException):
    def __init__(self):
        super().__init__("RATE_LIMIT_EXCEEDED", "Too many requests", 429)
```

### `shared/schemas.py`

```python
from pydantic import BaseModel
from typing import Generic, TypeVar, Any

T = TypeVar("T")

class SuccessResponse(BaseModel, Generic[T]):
    data: T
    message: str = "success"

class ErrorResponse(BaseModel):
    error: str        # machine-readable e.g. "VIDEO_NOT_FOUND"
    message: str      # human-readable  e.g. "Video not found"
    detail: Any = None

class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
```

---

## 3. Standard main.py Template

```python
# app/main.py — standard template for every FastAPI service
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from shared.exceptions import AppException

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect()
    await redis_client.connect()
    await kafka_producer.start()       # only if service produces
    asyncio.create_task(consumer.consume())  # only if service consumes
    yield
    # Shutdown
    await kafka_producer.stop()
    await redis_client.close()
    await db.close()

app = FastAPI(lifespan=lifespan)

# ── Exception Handlers ─────────────────────────────────────────────────
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code,
        content={"error": exc.error, "message": exc.message, "detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
        content={"error": "VALIDATION_ERROR", "message": "Invalid input",
                 "detail": exc.errors()})

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    await error_logger.log(SERVICE_NAME, exc, request)
    return JSONResponse(status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"})
```

---

## 4. Standard config.py Template

```python
# app/config.py — standard template
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    POSTGRES_HOST     : str
    POSTGRES_PORT     : int = 5432
    POSTGRES_USER     : str
    POSTGRES_PASSWORD : str
    POSTGRES_DB       : str
    REDIS_HOST        : str = "redis"
    REDIS_PORT        : int = 6379
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"

    @property
    def POSTGRES_URL(self) -> str:
        return (f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

---

## 5. Standard Response Format

**Every endpoint** returns one of these shapes:

```json
// Success
{ "data": { ... }, "message": "success" }

// Success (list)
{ "items": [...], "total": 100, "page": 1, "limit": 20 }

// Error
{ "error": "RESOURCE_NOT_FOUND", "message": "Human readable text", "detail": null }
```

**Error codes per HTTP status:**

| Status | Error Code | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed request |
| 401 | `UNAUTHORIZED` | No session / expired session |
| 403 | `FORBIDDEN` | Authenticated but not allowed |
| 404 | `{RESOURCE}_NOT_FOUND` | Entity does not exist |
| 409 | `CONFLICT` | Duplicate (e.g. email already exists) |
| 422 | `VALIDATION_ERROR` | Pydantic schema violation |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 503 | `SERVICE_UNAVAILABLE` | Dependency down |

---

## 6. Kafka Partition Key Strategy

All Kafka producers must set `key=entity_id.encode()` so that all events for the same entity land on the same partition (ensuring ordered processing):

```python
await producer.send(
    topic="viewer-interaction-events",
    key=event.videoId.encode(),   # ← partition key
    value=payload
)
```

---

## 7. MongoDB Error Logger

Every service logs unhandled exceptions to MongoDB `error_logs`:

```python
# app/logger.py
from motor.motor_asyncio import AsyncIOMotorClient

class ErrorLogger:
    def __init__(self, service_name: str, mongo_url: str):
        self.client = AsyncIOMotorClient(mongo_url)
        self.col = self.client["videoplatform"]["error_logs"]
        self.service = service_name

    async def log(self, exc: Exception, request=None, context: dict = None):
        await self.col.insert_one({
            "service": self.service,
            "level": "ERROR",
            "message": str(exc),
            "stack": traceback.format_exc(),
            "context": context or {},
            "occurredAt": datetime.utcnow()
        })
```

---

## 8. Standard Service Folder Structure

```
services/{service-name}/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py            ← FastAPI factory, lifespan, exception handlers
│   ├── config.py          ← Pydantic BaseSettings
│   ├── database.py        ← SQLAlchemy async engine + session factory
│   ├── redis_client.py    ← Redis connection singleton
│   ├── kafka_producer.py  ← (if service produces events)
│   ├── consumer.py        ← (if service consumes events)
│   ├── models.py          ← SQLAlchemy ORM models
│   ├── exceptions.py      ← Re-export + service-specific exceptions
│   ├── logger.py          ← MongoDB ErrorLogger instance
│   └── {domain}/
│       ├── router.py
│       ├── service.py
│       ├── repository.py  ← DB queries only
│       ├── cache.py       ← Redis operations only
│       └── schemas.py     ← Pydantic request/response (domain-specific)
└── tests/
```

---

## 9. Alembic Migrations

Each service that owns a PostgreSQL table runs Alembic. Migrations are applied at container startup:

```dockerfile
# In Dockerfile CMD
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
```

Migration files live in `services/{service}/alembic/versions/`.

---

## 10. Idempotency in Kafka Consumers

All Kafka consumers must be idempotent — check state before processing to handle redelivered messages:

```python
async def process(event: dict):
    video = await repo.get_video(event["videoId"])
    if video.status in ("ready", "failed"):
        return   # already processed — skip silently
    # proceed with processing...
```

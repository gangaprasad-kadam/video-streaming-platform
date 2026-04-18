# Copilot Instructions — Distributed Video Streaming Platform

## Project Overview

A distributed video streaming platform built with FastAPI microservices, React frontend, Kafka event bus, Redis, PostgreSQL, MongoDB, and NGINX gateway.

**Stack:** Python 3.10 (FastAPI) · React 18 (Vite) · Docker Compose · Apache Kafka · Redis · PostgreSQL · MongoDB · NGINX  
**Auth:** Session-based (HttpOnly cookie + Redis, no JWT)  
**Unique Feature:** 🔥 Viewer Behavior Heatmap Engine  
**Root:** `services/` contains all backend services; `services/shared/` is a Python module mounted into every service.

---

## Current State (Progress: 3 / 10 Phases)

| Phase | Status | Service(s) |
|-------|--------|------------|
| 1 — Infrastructure & Skeleton | ✅ Done | Docker Compose, Kafka, Redis, PostgreSQL, NGINX, `shared/` |
| 2 — User Service | ✅ Done | `user-service` |
| 3 — Video Service | ✅ Done | `video-service` |
| 4 — Processing Pipeline | 🔲 Not Started | `encoding-worker`, `thumbnail-worker` |
| 5 — Streaming Service | 🔲 Not Started | `streaming-service` |
| 6 — AI Summarization | 🔲 Not Started | `summarization-service` |
| 7 — Trending & Recommendations | 🔲 Not Started | `trending-service` |
| 8 — Heatmap Engine ⭐ | 🔲 Not Started | `event-ingestion`, `heatmap-aggregator`, `heatmap-api` |
| 9 — Frontend | 🔲 Not Started | `frontend/` |
| 10 — Integration & Docs | 🔲 Not Started | E2E tests, final compose |

**Next buildable phases (all dependencies met):** Phase 4, Phase 7, Phase 8a

---

## Three-Layer Architecture (MANDATORY for all services)

Every domain module MUST follow this exact structure:

```
services/{service-name}/
├── Dockerfile
├── requirements.txt
├── alembic.ini             ← if DB migrations needed
├── pytest.ini
├── app/
│   ├── main.py             ← FastAPI app, lifespan hooks, exception handlers
│   ├── config.py           ← pydantic-settings BaseSettings
│   ├── database.py         ← SQLAlchemy async engine + Base + get_db
│   ├── redis_client.py     ← Redis singleton + get_redis
│   ├── models.py           ← SQLAlchemy ORM models (service-wide)
│   ├── exceptions.py       ← Service-specific exceptions (extend shared/)
│   └── {domain}/           ← e.g. auth/, users/, videos/
│       ├── __init__.py
│       ├── handler/        ← LAYER 1: HTTP routes
│       │   ├── __init__.py
│       │   └── router.py   ← APIRouter, Depends(), request/response wiring
│       ├── utils/          ← LAYER 2: Business logic + helpers
│       │   ├── __init__.py
│       │   ├── service.py  ← Orchestration, business rules (no direct DB/Redis)
│       │   ├── schemas.py  ← Pydantic request/response models
│       │   └── cache.py    ← Redis helpers (if applicable)
│       └── dao/            ← LAYER 3: Data access
│           ├── __init__.py
│           └── repository.py ← SQLAlchemy queries only
├── migrations/             ← Alembic migrations (if DB service)
│   ├── env.py
│   └── versions/
└── tests/
    ├── conftest.py
    └── test_{domain}.py
```

**Layer rules (enforce strictly):**
- `handler/router.py` → calls `utils/service.py` only. Never touches `dao/` directly.
- `utils/service.py` → calls `dao/repository.py` and `utils/cache.py`. No HTTP concerns.
- `dao/repository.py` → raw SQLAlchemy queries only. No business logic.
- No layer skipping: Router → Service → Repository/Cache.

**Import pattern:**
```python
# In handler/router.py:
from app.{domain}.utils import service as {domain}_service
from app.{domain}.utils.schemas import MyRequest, MyResponse
from app.{domain}.utils.cache import get_cached_x

# In utils/service.py:
from app.{domain}.dao import repository as repo
from app.{domain}.utils.cache import set_x, invalidate_x

# In main.py:
from app.{domain}.handler.router import router as {domain}_router
```

---

## Implemented Services

### user-service (port 8001)
- `POST /auth/register` — bcrypt hash, unique email+username check
- `POST /auth/login` — verify credentials, set `session_id` HttpOnly cookie
- `POST /auth/logout` — delete session from Redis
- `GET /users/me` — return profile from session
- **DB:** PostgreSQL `users` table; **Cache:** Redis sessions (`session:{id}`, 24h sliding TTL)
- **Structure:** `app/auth/` and `app/users/` each with `handler/`, `utils/`, `dao/`

### video-service (port 8002)
- `POST /videos/upload` — multipart, saves to `/media/uploads/`, publishes `video.uploaded` Kafka event
- `GET /videos/{id}` — cache-aside (Redis 5min TTL)
- `GET /videos` — paginated list with optional `creator_id` filter
- `PATCH /videos/{id}` — creator-only update, invalidates cache
- `GET /videos/{id}/status` — polling endpoint
- `PATCH /internal/videos/{id}/status` — called by workers to advance lifecycle
- **Status lifecycle:** `uploading → processing → ready | failed` (idempotent terminal states)
- **DB:** PostgreSQL `videos` table; **Kafka:** producer to `video.uploaded`
- **Structure:** `app/videos/` with `handler/`, `utils/`, `dao/`

---

## Shared Module (`services/shared/`)

```python
# shared/exceptions.py — AppException hierarchy
class AppException(Exception): ...
class NotFoundError(AppException): ...    # 404, error_code="NOT_FOUND"
class AuthError(AppException): ...        # 401, error_code="UNAUTHORIZED"
class ForbiddenError(AppException): ...   # 403, error_code="FORBIDDEN"
class ConflictError(AppException): ...    # 409, error_code="CONFLICT"
class RateLimitError(AppException): ...   # 429, error_code="RATE_LIMITED"

# shared/schemas.py — Response envelopes
class SuccessResponse[T](BaseModel): data: T
class PagedResponse[T](BaseModel): data: list[T]; total: int; page: int; page_size: int
class ErrorResponse(BaseModel): error: str; message: str; detail: ...
```

The `shared/` directory is mounted as a volume into all services and added to `PYTHONPATH`.

---

## Key Conventions

### Response Format
All endpoints return `SuccessResponse[T]` or `PagedResponse[T]` from `shared/schemas.py`.  
Error responses: `{"error": "ERROR_CODE", "message": "...", "detail": ...}` — handled by `AppException` handler in `main.py`.

### Authentication
- Cookie name: `session_id` (HttpOnly, samesite=lax)
- Redis key: `session:{session_id}` → user_id (string UUID)
- Session TTL: 24h sliding window (refreshed on every authenticated request)
- No JWT — pure Redis session store

### Kafka
- Bootstrap servers: `kafka:9092`
- Key: always `entity_id.encode()` for partition ordering
- Consumers must be idempotent (check state before processing, handle redelivery)

### Database
- All services use PostgreSQL via `asyncpg` + SQLAlchemy async
- Alembic runs `upgrade head` at container startup (in Dockerfile CMD)
- UUIDs as primary keys (`uuid.uuid4()`)
- Timestamps: `created_at`, `updated_at` with `server_default=func.now()`

### Config
```python
# Each service has app/config.py:
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str = "postgresql+asyncpg://..."
    REDIS_URL: str = "redis://redis:6379/0"
```

### Error Logging
Unhandled exceptions → MongoDB `error_logs` via Motor (planned — not yet implemented in phases 1-3).

---

## Next Actions (Phase 4 — Processing Pipeline)

Build two Kafka consumer workers triggered by `video.uploaded` events:

### encoding-worker
- Kafka consumer: topic `video.uploaded`
- FFmpeg HLS transcoding: `video.mp4` → `index.m3u8` + `.ts` segments in `/media/hls/{videoId}/`
- FFprobe: extract duration
- On success: call `PATCH /internal/videos/{id}/status` with `{"status": "processing"}` then `{"status": "ready", "hls_path": "...", "duration": ...}`
- On failure: call status endpoint with `{"status": "failed"}`
- Publishes `video.processed` Kafka event
- Logs to MongoDB `processing_logs`
- Must be idempotent: skip if video already `ready` or `failed`

### thumbnail-worker
- Kafka consumer: topic `video.uploaded`
- FFmpeg frame extraction at `t=5s`: → `/media/thumbnails/{videoId}.jpg`
- On success: call status endpoint with `thumbnail_path`
- Idempotent

### New service structure:
```
services/encoding-worker/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py          ← start/stop Kafka consumer
    ├── config.py
    ├── consumer.py      ← Kafka consumer loop
    └── encoding/
        ├── handler/     ← Kafka event handler (not HTTP)
        ├── utils/       ← encoding logic (ffmpeg subprocess)
        └── dao/         ← MongoDB logging
```

### Alternative next phases (can be built in parallel with Phase 4):
- **Phase 7 (Trending):** Redis sorted sets + `viewer-interaction-events` consumer
- **Phase 8a (Event Ingestion):** `POST /events/interaction` → Kafka, Redis rate limiting

---

## Folder Structure

```
project/
├── .github/
│   └── copilot-instructions.md   ← this file
├── docker-compose.yml
├── .env / .env.example
├── nginx/
│   └── nginx.conf
├── services/
│   ├── shared/                   ← shared Python module
│   │   ├── exceptions.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── user-service/             ← Phase 2 ✅
│   ├── video-service/            ← Phase 3 ✅
│   ├── encoding-worker/          ← Phase 4 🔲
│   ├── thumbnail-worker/         ← Phase 4 🔲
│   ├── streaming-service/        ← Phase 5 🔲
│   ├── summarization-service/    ← Phase 6 🔲
│   ├── trending-service/         ← Phase 7 🔲
│   ├── event-ingestion/          ← Phase 8a 🔲
│   ├── heatmap-aggregator/       ← Phase 8b 🔲
│   └── heatmap-api/              ← Phase 8c 🔲
├── frontend/                     ← Phase 9 🔲
└── docs/
    ├── ROADMAP.md
    ├── ARCHITECTURE.md
    ├── DATABASE.md
    └── HEATMAP.md
```

---

## Testing Pattern

Each service uses:
- `pytest` + `pytest-asyncio` (strict mode)
- SQLite in-memory (`aiosqlite`) for DB — no real Postgres needed
- `AsyncMock` for Redis
- `patch.object` for Kafka producer
- `httpx.AsyncClient` with `ASGITransport` for endpoint testing
- FastAPI `dependency_overrides` for `get_db` and `get_redis`

Run tests from service root:
```bash
cd services/user-service && python3 -m pytest tests/ -v
cd services/video-service && python3 -m pytest tests/ -v
```

When patching service settings in tests, use the full three-layer path:
```python
# CORRECT:
patch("app.videos.utils.service.settings.MEDIA_ROOT", str(tmp_path))
# WRONG (old flat structure):
patch("app.videos.service.settings.MEDIA_ROOT", str(tmp_path))
```

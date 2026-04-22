# Copilot Instructions — Distributed Video Streaming Platform

## Project Overview

A distributed video streaming platform built with FastAPI microservices, React frontend, Kafka event bus, Redis, PostgreSQL, MongoDB, and NGINX gateway.

**Stack:** Python 3.11 (FastAPI) · React 18 (Vite) · Docker Compose · Apache Kafka · Redis · PostgreSQL · MongoDB · NGINX  
**Auth:** Session-based (HttpOnly cookie + Redis, no JWT)  
**Unique Feature:** 🔥 Viewer Behavior Heatmap Engine  
**Root:** `services/` contains all backend services; `services/shared/` is a Python module mounted into every service.

| Service | Port | Responsibility |
|---------|------|----------------|
| user-service | 8001 | Registration, login, session auth (Redis) |
| video-service | 8002 | Video upload, metadata CRUD, Kafka events |
| streaming-service | 8003 | HLS manifest & segment delivery |
| summarization-service | 8004 | Whisper transcription + DistilBART summary |
| trending-service | 8005 | Leaderboard + recommendations (Redis sorted sets) |
| event-ingestion | 8006 | `POST /events/interaction` → rate limit → Kafka |
| heatmap-aggregator | 8007 | Kafka consumer → bucket scoring → Redis + MongoDB |
| heatmap-api | 8008 | Heatmap read API (all-time / live / highlights) |
| encoding-worker | — | Kafka consumer → FFmpeg HLS transcode |
| thumbnail-worker | — | Kafka consumer → FFmpeg thumbnail extraction |

---

## Current State (Progress: 10 / 12 Services Complete)

| Phase | Status | Service(s) |
|-------|--------|------------|
| 1 — Infrastructure & Skeleton | ✅ Done | Docker Compose, Kafka, Redis, PostgreSQL, NGINX, `shared/` |
| 2 — User Service | ✅ Done | `user-service` |
| 3 — Video Service | ✅ Done | `video-service` |
| 4 — Processing Pipeline | ✅ Done | `encoding-worker`, `thumbnail-worker` |
| 5 — Streaming Service | ✅ Done | `streaming-service` |
| 6 — AI Summarization | ✅ Done | `summarization-service` |
| 7 — Trending & Recommendations | ✅ Done | `trending-service` |
| 8a — Event Ingestion | ✅ Done | `event-ingestion` |
| 8b — Heatmap Aggregator | ✅ Done | `heatmap-aggregator` |
| 8c — Heatmap API | ✅ Done | `heatmap-api` |
| 9 — Frontend | 🔲 Not Started | `frontend/` |
| 10 — Integration & Docs | 🔲 Not Started | E2E tests, final compose |

**Next buildable phases (all dependencies met):** Phase 9 (Frontend), Phase 10 (Integration)

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

### streaming-service (port 8003)
- `GET /stream/{videoId}/index.m3u8` — serve HLS manifest; Redis cache-aside (5min TTL), checks video-service for ready status; returns 425 if not ready
- `GET /stream/{videoId}/{segment}` — serve HLS `.ts` segment file; supports HTTP range requests for seeking
- `DELETE /internal/{videoId}/cache` — invalidate cached manifest (called after re-encoding)
- **Cache:** Redis `manifest:{videoId}` (5min TTL), `hls_path:{videoId}`
- **Structure:** `app/stream/` with `handler/`, `utils/` (no DB — stateless file serving)

### summarization-service (port 8004)
- Kafka consumer: `video.processed` → Whisper transcription → DistilBART summarization → PostgreSQL
- `GET /summary/{videoId}` — cache-aside: Redis (1h TTL) → PostgreSQL fallback → 404
- **DB:** PostgreSQL `video_summaries` table (transcript, summary, key_moments JSONB)
- **Cache:** Redis `summary:{videoId}`, 1h TTL
- **AI:** OpenAI Whisper (`base` model) for transcription, DistilBART for summarization
- CPU-heavy AI calls run in thread executor; models pre-downloaded at Docker build time
- **Structure:** `app/summary/` with `handler/` (router + consumer), `utils/`, `dao/`

### trending-service (port 8005)
- Kafka consumer: `viewer-interaction-events` → Redis `ZINCRBY` scoring
- `GET /trending` — top N videos from Redis sorted set (sub-ms reads)
- `GET /recommendations/{userId}` — 60% trending + 40% creator-based, minus watched
- Score decay: hourly 0.9× multiplier via background task
- **DB:** PostgreSQL `watch_history` table (upserted on `PLAY` events)
- **Structure:** `app/trending/` with `handler/`, `utils/`, `dao/`

### event-ingestion (port 8006)
- `POST /events/interaction` → validates event, Redis rate limiting, async Kafka publish → 202
- Kafka topic: `viewer-interaction-events`
- **Structure:** `app/events/` with `handler/`, `utils/`

### heatmap-aggregator (port 8007, background worker)
- Kafka consumer: `viewer-interaction-events` → 5-second bucket scoring → Redis + MongoDB
- **Cache:** Redis heatmap buckets; **DB:** MongoDB `heatmap_data` collection
- **Structure:** `app/heatmap/` with `handler/` (consumer), `utils/`, `dao/`

### heatmap-api (port 8008)
- `GET /heatmap/{videoId}` — all-time heatmap from MongoDB
- `GET /heatmap/{videoId}/live` — 5-minute sliding window from Redis
- `GET /heatmap/{videoId}/highlights` — top-scoring segments
- **Structure:** `app/heatmap/` with `handler/`, `utils/`, `dao/`

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

| Topic | Producer | Consumers |
|-------|----------|-----------|
| `video.uploaded` | video-service | encoding-worker, thumbnail-worker |
| `video.processed` | encoding-worker | summarization-service |
| `viewer-interaction-events` | event-ingestion | trending-service, heatmap-aggregator |

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
Unhandled exceptions → MongoDB `error_logs` via Motor (planned for all services). MongoDB is currently used by `heatmap-aggregator` for heatmap bucket storage.

---

## Next Actions (Phase 9 — Frontend)

Build the React 18 + Vite frontend:

- Video player with HLS.js
- Auth pages (register / login)
- Upload flow with processing status polling
- Trending & recommendations feed
- AI summary panel alongside the player
- Heatmap overlay on video progress bar (fires `POST /events/interaction` on PLAY, PAUSE, SEEK, REWIND)

### After frontend (Phase 10 — Integration & Testing):
- Full `docker compose up` smoke tests
- End-to-end flow: upload → encode → stream → summarize → trending → heatmap
- Final documentation pass

---

## Folder Structure

```
project/
├── .github/
│   └── copilot-instructions.md   ← this file
├── docker-compose.yml
├── .env / .env.example
├── start.sh
├── nginx/
│   └── nginx.conf
├── services/
│   ├── shared/                   ← shared Python module
│   │   ├── exceptions.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── user-service/             ← Phase 2 ✅
│   ├── video-service/            ← Phase 3 ✅
│   ├── encoding-worker/          ← Phase 4 ✅
│   ├── thumbnail-worker/         ← Phase 4 ✅
│   ├── streaming-service/        ← Phase 5 ✅
│   ├── summarization-service/    ← Phase 6 ✅
│   ├── trending-service/         ← Phase 7 ✅
│   ├── event-ingestion/          ← Phase 8a ✅
│   ├── heatmap-aggregator/       ← Phase 8b ✅
│   └── heatmap-api/              ← Phase 8c ✅
├── frontend/                     ← Phase 9 🔲
└── docs/
    ├── ROADMAP.md
    ├── ARCHITECTURE.md
    ├── DATABASE.md
    ├── HEATMAP.md
    ├── diagrams/                 ← architecture diagrams (PNG)
    ├── service-working/          ← per-service technical reference (01–10)
    └── test/                     ← per-service Postman testing guides (01–09)
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
cd services/trending-service && python3 -m pytest tests/ -v
cd services/event-ingestion && python3 -m pytest tests/ -v
cd services/heatmap-api && python3 -m pytest tests/ -v
```

When patching service settings in tests, use the full three-layer path:
```python
# CORRECT:
patch("app.videos.utils.service.settings.MEDIA_ROOT", str(tmp_path))
# WRONG (old flat structure):
patch("app.videos.service.settings.MEDIA_ROOT", str(tmp_path))
```

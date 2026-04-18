# Video Service — Complete Technical Reference

## 1. What Is This Service?

The **video-service** handles everything related to video lifecycle management:
- Accepting file uploads from authenticated users
- Storing raw video files to the shared media volume
- Publishing `video.uploaded` events to Kafka (triggering the processing pipeline)
- Tracking video status through its lifecycle: `uploading → processing → ready/failed`
- Serving video metadata (title, description, status, HLS path, thumbnail, duration)
- Receiving internal status updates from workers (encoding-worker, thumbnail-worker)

**Port:** `8002` (internal Docker network: `video-service:8002`)  
**Database:** PostgreSQL (`videodb`)  
**Cache:** Redis DB 1 (`redis://redis:6379/1`) — video metadata cache  
**Kafka:** Produces to `video.uploaded` topic  
**Framework:** FastAPI + SQLAlchemy (async) + asyncpg + aiokafka

---

## 2. Folder Structure

```
video-service/
├── app/
│   ├── main.py              ← FastAPI app factory, lifespan, error handlers
│   ├── config.py            ← Pydantic-Settings (reads .env)
│   ├── database.py          ← SQLAlchemy async engine + get_db()
│   ├── redis_client.py      ← Singleton Redis connection + get_redis()
│   ├── kafka_producer.py    ← AIOKafkaProducer singleton + publish()
│   ├── auth_utils.py        ← Session cookie → user_id (reads from Redis)
│   ├── models.py            ← Video + VideoStatus SQLAlchemy ORM model
│   ├── exceptions.py        ← Service-specific exceptions
│   │
│   └── videos/              ← Video domain
│       ├── handler/
│       │   └── router.py    ← HTTP routes (public + internal)
│       ├── utils/
│       │   ├── service.py   ← Business logic (upload, get, list, patch, update_status)
│       │   ├── cache.py     ← Redis cache helpers (set/get/invalidate video meta)
│       │   └── schemas.py   ← Pydantic request/response models
│       └── dao/
│           └── repository.py← SQLAlchemy queries (CRUD on videos table)
│
├── migrations/
│   └── versions/
│       └── 0001_create_videos_table.py
├── tests/
│   ├── conftest.py          ← fixtures: SQLite, mock Redis, mock Kafka, temp media dir
│   └── test_videos.py       ← 9 tests covering all endpoints
├── Dockerfile
├── alembic.ini
├── requirements.txt
└── pytest.ini
```

---

## 3. Three-Layer Architecture

```
HTTP Request
    │
    ▼
handler/router.py          ← Routes only. Reads form data, files, calls service.
    │
    ▼
utils/service.py           ← All business logic:
    │                         - file I/O (aiofiles)
    │                         - Kafka event publishing
    │                         - ownership checks
    │                         - cache-aside pattern
    ├──► utils/cache.py    ← Redis cache (set/get/invalidate video metadata)
    └──► dao/repository.py ← All SQL queries
    │
    ▼
dao/repository.py          ← Raw SQLAlchemy only. No business logic.
```

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@postgres:5432/videodb` | Async PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/1` | Redis DB 1 (video cache) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `MEDIA_ROOT` | `/media` | Shared Docker volume mount point |
| `DEBUG` | `False` | SQLAlchemy query logging |

---

## 5. Database Schema (models.py + Migration)

### Table: `videos`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique video identifier |
| `title` | VARCHAR(255) | NOT NULL | Video title |
| `description` | TEXT | NULLABLE | Optional description |
| `creator_id` | UUID | NOT NULL | FK-style reference to user-service user (no real FK — services are decoupled) |
| `file_path` | TEXT | NOT NULL | Full path on media volume to original uploaded file |
| `hls_path` | TEXT | NULLABLE | Path to HLS `.m3u8` manifest (set after encoding) |
| `thumbnail_path` | TEXT | NULLABLE | Path to thumbnail image (set after thumbnail generation) |
| `duration` | NUMERIC(10,2) | NULLABLE | Video duration in seconds (set after encoding) |
| `status` | ENUM | NOT NULL, DEFAULT 'uploading' | Lifecycle state |
| `file_size_bytes` | BIGINT | NULLABLE | Original file size |
| `mime_type` | VARCHAR(50) | NULLABLE | e.g. `video/mp4` |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Upload time |
| `updated_at` | TIMESTAMPTZ | DEFAULT now(), ON UPDATE | Last modification time |

### VideoStatus Enum

```
uploading   → file is being saved to disk
processing  → encoding-worker is transcoding the video
ready       → HLS transcoding complete; video is streamable
failed      → encoding failed
```

**State transitions (valid):**
```
uploading → processing → ready
uploading → processing → failed
```

**Terminal states:** `ready` and `failed` — once reached, status cannot change.
However, metadata fields (`hls_path`, `thumbnail_path`, `duration`) CAN still be updated
(e.g. thumbnail-worker finishing after encoding-worker already set status to "ready").

**Indexes:**
- `idx_videos_creator` on `creator_id` — fast queries by user
- `idx_videos_status` on `status` — fast filtering by status
- `idx_videos_created_at` DESC on `created_at` — fast chronological listing

---

## 6. Kafka Producer (kafka_producer.py)

Uses `AIOKafkaProducer` — async Kafka producer initialized on app startup.

```python
_producer = AIOKafkaProducer(
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode(),
)
```

**`publish(topic, key, value)` function:**
- Serializes `value` dict to JSON bytes
- Sends message with `key` as partition key (ensures same video goes to same partition)
- Uses `send_and_wait` — waits for broker acknowledgement before returning

**Topic produced to:**

| Topic | Triggered by | Consumers |
|---|---|---|
| `video.uploaded` | `POST /videos/upload` | encoding-worker, thumbnail-worker |

**Event payload for `video.uploaded`:**
```json
{
  "videoId": "550e8400-...",
  "creatorId": "user-uuid",
  "filePath": "/media/uploads/video-uuid.mp4",
  "mimeType": "video/mp4",
  "title": "My Video",
  "uploadedAt": "2024-01-15T10:30:00"
}
```

---

## 7. Session Auth (auth_utils.py)

The video-service **does not call user-service** to verify sessions. Instead, it reads the same
Redis instance (DB 1, but the session key is stored in DB 0 by user-service).

Wait — actually the video-service has its own Redis URL (`redis://redis:6379/1`), but session keys
were written to DB 0 by user-service. This works because `REDIS_URL` for video-service points to
DB 1 **for video cache**, but `get_current_user_id` reads `session:{id}` — these keys were set
with TTL by user-service on DB 0.

> **Note:** In production, `auth_utils.py` should connect to Redis DB 0 for session validation
> and Redis DB 1 for video cache. The current implementation reads sessions from whatever DB
> the `REDIS_URL` points to. This works in tests because we mock Redis entirely.

**Flow:**
```python
session_id = request.cookies.get("session_id")
user_id = await redis.get(f"session:{session_id}")
await redis.expire(f"session:{session_id}", 86400)  # refresh sliding TTL
return user_id
```

---

## 8. Redis Cache Design (utils/cache.py)

| Key | Value | TTL |
|---|---|---|
| `video:{videoId}` | JSON-serialized VideoResponse dict | 300s (5 min) |

**Cache-aside pattern for GET /videos/{id}:**
```
GET request → check Redis
    → HIT:  deserialize JSON, return immediately (no DB query)
    → MISS: query PostgreSQL, serialize result, store in Redis, return
```

**Cache invalidation:**
Any write operation (PATCH metadata, status update) calls `invalidate_video_cache(redis, video_id)`
which deletes the key. Next GET will repopulate from DB.

---

## 9. File Storage

Files are stored on the shared Docker volume mounted at `MEDIA_ROOT` (`/media`):

```
/media/
├── uploads/        ← Original uploaded video files
│   ├── {video-uuid}.mp4
│   └── ...
├── hls/            ← HLS output (created by encoding-worker)
│   └── {video-uuid}/
│       ├── index.m3u8
│       ├── segment000.ts
│       └── ...
└── thumbnails/     ← Thumbnail images (created by thumbnail-worker)
    ├── {video-uuid}.jpg
    └── ...
```

**Upload flow:**
1. Write file to temp path: `uploads/{placeholder-uuid}.ext`
2. Create DB record → get real UUID
3. Rename file to real UUID: `uploads/{real-uuid}.ext`
4. Update `file_path` in DB

This two-step rename is necessary because the UUID is generated by the DB, not known in advance.

---

## 10. API Endpoints

### Health Check

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service liveness check |

**Response:** `{ "status": "ok", "service": "video-service" }`

---

### Public Video Endpoints (`/videos`)

#### POST `/videos/upload`

Upload a new video. Accepts multipart form data.

**Auth Required:** Yes (session cookie)

**Request:** `multipart/form-data`
```
title        : str (required)  — video title
description  : str (optional)  — video description
file         : file (required)  — video file (mp4, etc.)
```

**Success Response — 201 Created:**
```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "My First Video",
    "description": "A test video",
    "status": "uploading",
    "creator_id": "user-uuid",
    "file_path": "/media/uploads/video-uuid.mp4",
    "hls_path": null,
    "thumbnail_path": null,
    "duration": null,
    "file_size_bytes": 5242880,
    "mime_type": "video/mp4",
    "created_at": "2024-01-15T10:30:00"
  }
}
```

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 401 | `UNAUTHORIZED` | No valid session cookie |
| 422 | `VALIDATION_ERROR` | Missing required fields |

**Internal Flow:**
```
POST /videos/upload (multipart)
    → get_current_user_id() ← validates session cookie via Redis
    → video_service.upload_video(db, redis, file, title, description, user_id)
        1. Generate placeholder UUID
        2. Build file_path = {MEDIA_ROOT}/uploads/{placeholder}.{ext}
        3. os.makedirs(dir, exist_ok=True)
        4. aiofiles.open(file_path, "wb") → write content
        5. repo.create_video(db, ...) → INSERT into videos table, status="uploading"
        6. Rename file to real UUID path
        7. UPDATE file_path in DB
        8. kafka_producer.publish("video.uploaded", key=video_id, value={...})
    ← return 201 VideoResponse
```

---

#### GET `/videos/{video_id}`

Fetch metadata for a single video.

**Auth Required:** No (public endpoint)

**Success Response — 200 OK:**
```json
{
  "data": {
    "id": "...",
    "title": "My Video",
    "status": "ready",
    "hls_path": "/media/hls/uuid/index.m3u8",
    "thumbnail_path": "/media/thumbnails/uuid.jpg",
    "duration": 125.5,
    ...
  }
}
```

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 404 | `VIDEO_NOT_FOUND` | No video with that UUID |

**Cache behavior:**
- Checks `video:{video_id}` in Redis first (TTL 5 min)
- On miss: fetches from PostgreSQL, stores in Redis
- Returns cached data when available (fast path)

---

#### GET `/videos`

List videos with pagination. Optionally filter by creator.

**Auth Required:** No (public)

**Query Parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (1-indexed) |
| `limit` | int | 20 | Items per page |
| `creator_id` | UUID string | None | Filter to specific creator's videos |

**Success Response — 200 OK:**
```json
{
  "data": [ { ...VideoResponse... }, { ...VideoResponse... } ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

**Note:** Results are ordered by `created_at DESC` (newest first). No Redis cache — always hits DB.

---

#### PATCH `/videos/{video_id}`

Update a video's title and/or description. Only the creator can do this.

**Auth Required:** Yes (session cookie)

**Request Body:**
```json
{
  "title": "Updated Title",       // optional
  "description": "New description" // optional
}
```

**Success Response — 200 OK:** Updated VideoResponse

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 401 | `UNAUTHORIZED` | No valid session |
| 403 | `FORBIDDEN` | Authenticated user is not the video creator |
| 404 | `VIDEO_NOT_FOUND` | No video with that UUID |

**Internal Flow:**
```
PATCH /videos/{video_id}
    → get_current_user_id() ← session validation
    → video_service.patch_video(db, redis, video_id, user_id, title, description)
        → repo.get_by_id(db, video_id) ← fetch video
        → check: str(video.creator_id) == requester_id  (403 if mismatch)
        → repo.update_video(db, video, title, description)
        → invalidate_video_cache(redis, video_id) ← bust Redis cache
    ← return updated VideoResponse
```

---

#### GET `/videos/{video_id}/status`

Lightweight status check — returns only ID + status. Does not use Redis cache.

**Auth Required:** No

**Success Response — 200 OK:**
```json
{
  "data": {
    "id": "550e8400-...",
    "status": "processing"
  }
}
```

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 404 | `VIDEO_NOT_FOUND` | No video with that UUID |

---

### Internal Endpoints (`/internal/videos`)

These endpoints are called **only by workers** (encoding-worker, thumbnail-worker). They are
**not exposed** through nginx — workers call the service directly over the Docker network.

#### PATCH `/internal/videos/{video_id}/status`

Update video status and/or metadata fields. Called by encoding-worker and thumbnail-worker.

**Auth Required:** No auth (internal network only, not exposed via nginx)

**Request Body:**
```json
{
  "status": "ready",
  "hls_path": "/media/hls/uuid/index.m3u8",   // optional
  "thumbnail_path": "/media/thumbnails/uuid.jpg", // optional
  "duration": 125.5                              // optional
}
```

**Success Response — 200 OK:** Updated VideoResponse

**Terminal State Handling (important design decision):**

If the video is already in a terminal state (`ready` or `failed`):
- Status is **NOT changed** (terminal = final)
- But `hls_path`, `thumbnail_path`, `duration` **CAN still be updated**
- This handles the race condition where thumbnail-worker finishes AFTER encoding-worker
  has already set status to "ready"

```python
if video.status.value in ("ready", "failed"):
    # Only update metadata fields, don't touch status
    if any(v is not None for v in (hls_path, thumbnail_path, duration)):
        video = await repo.update_video_fields(db, video, ...)
    return _to_response(video)  # status unchanged
```

**Who calls this:**

| Worker | Status set | Extra fields |
|---|---|---|
| encoding-worker | `processing` (start) | — |
| encoding-worker | `ready` (success) | `hls_path`, `duration` |
| encoding-worker | `failed` (error) | — |
| thumbnail-worker | — | `thumbnail_path` (in terminal-state update path) |

---

## 11. Error Response Format

All errors use this envelope:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "detail": null
}
```

| Error Code | HTTP Status | Cause |
|---|---|---|
| `UNAUTHORIZED` | 401 | No session or expired session |
| `FORBIDDEN` | 403 | Not the video creator |
| `VIDEO_NOT_FOUND` | 404 | Video UUID doesn't exist in DB |
| `VALIDATION_ERROR` | 422 | Invalid request body |

---

## 12. Startup & Shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()      # ping PostgreSQL
    await connect_redis()   # create Redis connection pool
    await start_producer()  # start AIOKafkaProducer, connect to broker
    yield
    await stop_producer()   # flush pending messages, close producer
    await close_redis()
    await close_db()
```

Connections are established once at startup, not per-request.

---

## 13. Docker Configuration

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY migrations/ ./migrations/
COPY app/ ./app/
RUN mkdir -p /media/uploads /media/hls /media/thumbnails
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8002"]
```

**Key differences from user-service:**
- Installs `gcc libpq-dev` (needed for `asyncpg` native extension compilation)
- Creates media subdirectories at build time
- Runs on port **8002**
- docker-compose mounts `./services/shared:/app/shared:ro` and `media_data:/media`

---

## 14. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `sqlalchemy[asyncio]` | 2.0.28 | Async ORM |
| `asyncpg` | 0.29.0 | Async PostgreSQL driver |
| `redis[asyncio]` | 5.0.3 | Async Redis client |
| `aiokafka` | 0.10.0 | Async Kafka producer |
| `aiofiles` | 23.2.1 | Async file I/O for large uploads |
| `python-multipart` | 0.0.9 | Multipart form data parsing (file uploads) |
| `pydantic[email]` | 2.6.4 | Schema validation |
| `pydantic-settings` | 2.2.1 | Config from environment |
| `alembic` | 1.13.1 | DB migrations |

---

## 15. Testing

**Test strategy:**
- **Database:** SQLite in-memory (`aiosqlite`) — no PostgreSQL needed
- **Redis:** AsyncMock with a Python `dict` as backing store
- **Kafka:** `patch.object(kp, "publish", ...)` — captures published events in a list
- **Media files:** `tmp_path` (pytest fixture) — temp directory for file writes

**Test fixtures (conftest.py):**
- `redis_mock` — mock Redis + dict store
- `kafka_mock` — captures all `publish()` calls as `[{topic, key, value}]`
- `client` — AsyncClient with all overrides, seeds `session:test-session-id` = known user UUID

**Test coverage (9 tests):**

| Test | What is tested |
|---|---|
| `test_upload_video_success_returns_201` | Successful upload, status=uploading |
| `test_upload_requires_auth` | Upload without cookie → 401 |
| `test_upload_publishes_kafka_event` | Kafka event published with correct fields |
| `test_get_video_by_id` | Fetch uploaded video by ID |
| `test_get_video_not_found_returns_404` | Unknown UUID → 404 |
| `test_list_videos_pagination` | page=1&limit=2 with 3 videos → 2 items, total=3 |
| `test_patch_video_as_creator` | Creator can update title |
| `test_patch_video_as_non_creator_returns_403` | Non-creator gets 403 |
| `test_status_transitions_uploading_to_processing_to_ready` | Full lifecycle + terminal-state idempotency |

**Run tests:**
```bash
cd services/video-service
python -m pytest tests/ -q
# Expected: 9 passed
```

---

## 16. Full Video Lifecycle Data Flow

```
BROWSER         NGINX         VIDEO-SERVICE      POSTGRES    REDIS    KAFKA
  │               │                │                │          │        │
  │─ POST /videos/upload ─────────►│                │          │        │
  │  (multipart: title, file)      │                │          │        │
  │               │                │─ validate session ────────►│        │
  │               │                │                │          │        │
  │               │                │─ write file to /media/uploads/      │
  │               │                │─ INSERT videos ────────────►│        │
  │               │                │─ rename file to real UUID           │
  │               │                │─ UPDATE file_path ─────────►│        │
  │               │                │─ publish video.uploaded ─────────────►
  │◄─ 201 {data: video, status=uploading} ──────────│          │        │
  │               │                │                │          │        │
  │ [Workers receive Kafka event]   │                │          │        │
  │               │                │                │          │        │
  │ ENCODING-WORKER:                │                │          │        │
  │               │ PATCH /internal/videos/{id}/status {status:processing}
  │               │                │─ UPDATE status ────────────►│        │
  │               │                │─ invalidate cache ──────────────────►│
  │               │                │                │          │        │
  │               │ PATCH /internal/videos/{id}/status {status:ready, hls_path, duration}
  │               │                │─ UPDATE status+hls+duration ────────►│
  │               │                │─ invalidate cache ──────────────────►│
  │               │                │                │          │        │
  │ THUMBNAIL-WORKER:               │                │          │        │
  │               │ PATCH /internal/videos/{id}/status {thumbnail_path}
  │               │                │─ status is "ready" → only UPDATE thumbnail_path
  │               │                │─ invalidate cache ──────────────────►│
  │               │                │                │          │        │
  │─ GET /videos/{id} ────────────►│                │          │        │
  │               │                │─ check cache ───────────────────────►│
  │               │                │  (MISS: query DB, cache result)       │
  │◄─ 200 {status:ready, hls_path, thumbnail_path, duration} ──│          │
```

---

## 17. Shared Module Usage

The video-service uses `shared/` module for:
- `shared.exceptions.AppException` — base exception class
- `shared.exceptions.ForbiddenError`, `NotFoundError` — base classes for service exceptions
- `shared.schemas.SuccessResponse[T]` — uniform `{data: T}` response envelope
- `shared.schemas.PagedResponse[T]` — paginated `{data: [], total, page, page_size}` envelope

The `shared/` folder is bind-mounted read-only at `/app/shared` in Docker.

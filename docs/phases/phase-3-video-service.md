# Phase 3 — Video Service

## Goal
A FastAPI microservice that handles video file uploads, metadata storage, and lifecycle management. On upload, it saves the file to a shared Docker volume and publishes a `video.uploaded` Kafka event to trigger downstream processing.

---

## Service Details

| Property | Value |
|---|---|
| Service name | `video-service` |
| Port | `8002` |
| Framework | FastAPI (Python) |
| Database | PostgreSQL (`videos` table) |
| Storage | Docker volume (`/media/uploads/`) |
| Event bus | Kafka producer → `video.uploaded` |
| Tests | Yes — upload + status transitions |

---

## Folder Structure

```
services/video-service/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── kafka_producer.py   ← aiokafka producer
│   ├── models.py
│   ├── exceptions.py       ← re-exports shared exceptions + service-specific ones
│   └── videos/
│       ├── router.py
│       ├── service.py
│       ├── repository.py   ← DB queries only
│       ├── cache.py        ← Redis operations only
│       └── schemas.py
└── tests/
    ├── conftest.py
    └── test_videos.py
```

---

## API Endpoints

```
POST /videos/upload
  Auth   : session cookie required
  Body   : multipart/form-data { file: <video>, title: str, description: str }
  Action : save file to volume, insert DB record (status=uploading),
           publish video.uploaded Kafka event, return metadata
  Response 201: { "data": { "id": uuid, "title": str, "status": "uploading", ... }, "message": "success" }
  Error 401: { "error": "UNAUTHORIZED", "message": "Not authenticated" }

GET /videos/:id
  Auth     : optional (public videos accessible without auth)
  Response : { "data": { "id", "title", "description", "status", "thumbnail_url",
               "duration", "creator_id", "created_at" }, "message": "success" }
  Error 404: { "error": "VIDEO_NOT_FOUND", "message": "Video with id '...' not found" }

GET /videos
  Query params: page=1, limit=20, creator_id=<uuid>
  Response: { "items": [...], "total": int, "page": int, "limit": int }

PATCH /videos/:id
  Auth   : session cookie (must be creator)
  Body   : { "title": str?, "description": str? }
  Response 200: { "data": { ...updated video object... }, "message": "success" }
  Error 403: { "error": "FORBIDDEN", "message": "Access denied" }
  Error 404: { "error": "VIDEO_NOT_FOUND", "message": "Video with id '...' not found" }

GET /videos/:id/status
  Response: { "data": { "id": uuid, "status": "uploading|processing|ready|failed" }, "message": "success" }
  (Frontend polls this to show upload progress)
```

---

## Video Status Lifecycle

```
                  ┌──────────┐
    upload req ──▶│ uploading│
                  └────┬─────┘
                       │ file saved, Kafka event published
                       ▼
                  ┌──────────┐
                  │processing│ ← encoding + thumbnail workers running
                  └────┬─────┘
                       │ video.processed Kafka event received
                       ▼
                  ┌────────┐
                  │  ready │ ← streamable
                  └────────┘

                  ┌────────┐
                  │ failed │ ← any worker error
                  └────────┘
```

Status is updated by an internal endpoint that processing workers call after consuming Kafka events.

---

## PostgreSQL Schema

```sql
CREATE TYPE video_status AS ENUM ('uploading', 'processing', 'ready', 'failed');

CREATE TABLE videos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    creator_id      UUID NOT NULL REFERENCES users(id),
    file_path       TEXT NOT NULL,          -- path on Docker volume
    hls_path        TEXT,                   -- set after encoding (Phase 4)
    thumbnail_path  TEXT,                   -- set after thumbnail gen (Phase 4)
    duration        DECIMAL(10,2),          -- seconds, set after encoding
    status          video_status NOT NULL DEFAULT 'uploading',
    file_size_bytes BIGINT,
    mime_type       VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_videos_creator    ON videos(creator_id);
CREATE INDEX idx_videos_status     ON videos(status);
CREATE INDEX idx_videos_created_at ON videos(created_at DESC);
```

---

## Kafka Event: `video.uploaded`

```json
{
  "videoId":   "uuid",
  "creatorId": "uuid",
  "filePath":  "/media/uploads/uuid.mp4",
  "mimeType":  "video/mp4",
  "title":     "My Video",
  "uploadedAt": "2026-03-31T12:00:00Z"
}
```

Published to topic `video.uploaded`, partition key = `videoId`.

---

## File Storage

```
Docker volume: media_volume  mounted at  /media/

/media/
├── uploads/         ← raw uploaded files (video-service writes here)
│   └── {videoId}.mp4
├── hls/             ← HLS output (encoding-worker writes here)
│   └── {videoId}/
│       ├── index.m3u8
│       └── segment_000.ts, segment_001.ts ...
└── thumbnails/      ← thumbnail images (thumbnail-worker writes here)
    └── {videoId}.jpg
```

All services that need to read/write media mount the same `media_volume`.

---

## Kafka Producer (aiokafka)

```python
# app/kafka_producer.py
from aiokafka import AIOKafkaProducer
import json

producer: AIOKafkaProducer = None

async def start_producer():
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode()
    )
    await producer.start()

async def publish(topic: str, key: str, value: dict):
    await producer.send_and_wait(
        topic,
        key=key.encode(),
        value=value
    )
```

---

## requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
aiokafka==0.10.0
aiofiles==23.2.1
python-multipart==0.0.9
pydantic-settings==2.2.1
alembic==1.13.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
```

---

## Tests

```
tests/test_videos.py
  ✅ test_upload_video_success_returns_201
  ✅ test_upload_requires_auth
  ✅ test_upload_publishes_kafka_event
  ✅ test_get_video_by_id
  ✅ test_get_video_not_found_returns_404
  ✅ test_list_videos_pagination
  ✅ test_patch_video_as_creator
  ✅ test_patch_video_as_non_creator_returns_403
  ✅ test_status_transitions_uploading_to_processing_to_ready
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| File write to volume | Sync (blocking, `aiofiles`) | Must complete before publishing Kafka event |
| PostgreSQL insert | Async (await) | Non-blocking via asyncpg |
| Kafka publish | Async (await) | Non-blocking via aiokafka |
| Return to client | After DB insert | Client gets `uploadedAt` response immediately; processing continues async |

---

## Standard Response Format

All endpoints wrap responses in `SuccessResponse` from `shared/schemas.py` (see **shared-patterns.md Section 5**):

```python
# videos/router.py example
from shared.schemas import SuccessResponse, PagedResponse

@router.post("/upload", status_code=201, response_model=SuccessResponse[VideoResponse])
async def upload_video(...):
    video = await video_service.upload(...)
    return SuccessResponse(data=VideoResponse.model_validate(video))

@router.get("", response_model=PagedResponse[VideoResponse])
async def list_videos(...):
    result = await video_service.list_videos(...)
    return PagedResponse(items=result.items, total=result.total, page=page, limit=limit)
```

```json
// POST /videos/upload → 201
{ "data": { "id": "uuid", "title": "My Video", "status": "uploading" }, "message": "success" }

// GET /videos/:id → 404
{ "error": "VIDEO_NOT_FOUND", "message": "Video with id '...' not found" }

// PATCH /videos/:id → 403
{ "error": "FORBIDDEN", "message": "Access denied" }
```

---

## Status Update Idempotency

When a processing worker calls the internal status update endpoint, check the current status before applying the transition to handle Kafka message redelivery (see **shared-patterns.md Section 10**):

```python
# videos/service.py
async def update_status(video_id: str, new_status: str) -> Video:
    video = await repo.get_video(video_id)
    if video.status in ("ready", "failed"):
        return video   # already terminal — skip silently (idempotent)
    video.status = new_status
    return await repo.save(video)
```

---

## References Shared Patterns

| Pattern | shared-patterns.md |
|---|---|
| Layered architecture (Router → Service → Repository → Cache) | Section 1 |
| Shared `services/shared/` module (`dependencies.py`, `exceptions.py`, `schemas.py`) | Section 2 |
| Standard `main.py` (lifespan, global exception handler) | Section 3 |
| Standard `config.py` template | Section 4 |
| Response envelope (`SuccessResponse`, `ErrorResponse`, `PagedResponse`) | Section 5 |
| Kafka partition key strategy (`key=videoId.encode()`) | Section 6 |
| Idempotency in Kafka consumers | Section 10 |

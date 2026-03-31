# 🔩 Low-Level Design (LLD)

## Table of Contents

1. [Layered Architecture](#1-layered-architecture)
2. [Service Internal Module Design](#2-service-internal-module-design)
3. [Class Diagrams](#3-class-diagrams)
4. [Sequence Diagrams](#4-sequence-diagrams)
5. [API Contracts](#5-api-contracts)
6. [Error Handling Strategy](#6-error-handling-strategy)
7. [Design Patterns Used](#7-design-patterns-used)
8. [Inter-Service Communication](#8-inter-service-communication)
9. [Configuration Management](#9-configuration-management)
10. [Security Design](#10-security-design)

---

## 1. Layered Architecture

Every microservice follows a strict **4-layer architecture** to keep concerns separated:

```
┌─────────────────────────────────────────────────────────┐
│                    REQUEST / EVENT                       │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│               ROUTER LAYER  (app/*/router.py)           │
│  • HTTP route definitions                               │
│  • Input validation (Pydantic schemas)                  │
│  • Auth dependency injection                            │
│  • Delegates to Service layer — zero business logic     │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│              SERVICE LAYER  (app/*/service.py)          │
│  • All business logic lives here                        │
│  • Orchestrates calls to Repository + Kafka + Cache     │
│  • Raises domain exceptions (caught by Router)          │
│  • Stateless — no DB/Redis connections directly         │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
┌──────────▼────────────┐  ┌──────────▼──────────────────┐
│   REPOSITORY LAYER    │  │      CACHE LAYER             │
│  (app/*/repository.py)│  │   (app/*/cache.py)           │
│                       │  │                              │
│  • SQLAlchemy queries │  │  • Redis get/set/expire      │
│  • Raw SQL if needed  │  │  • Cache-aside pattern       │
│  • Returns domain     │  │  • Returns None on miss      │
│    objects (not ORM)  │  └──────────────────────────────┘
└──────────┬────────────┘
           │
┌──────────▼────────────┐
│   DATABASE / INFRA    │
│  PostgreSQL · Redis   │
│  Kafka · MongoDB      │
└───────────────────────┘
```

### Naming Convention per Service

```
services/{service-name}/app/
├── main.py           ← FastAPI app factory, lifespan hooks
├── config.py         ← Pydantic BaseSettings (reads from env)
├── database.py       ← SQLAlchemy async engine + session factory
├── redis_client.py   ← Redis connection singleton
├── kafka_*.py        ← Producer / Consumer
├── models.py         ← SQLAlchemy ORM models
├── schemas.py        ← Pydantic request/response schemas
├── exceptions.py     ← Domain-specific exceptions
└── {domain}/
    ├── router.py     ← FastAPI APIRouter
    ├── service.py    ← Business logic
    ├── repository.py ← DB queries
    └── cache.py      ← Redis operations
```

---

## 2. Service Internal Module Design

### 2.1 User Service

```
app/
├── main.py
│     └── create_app() → FastAPI
│           ├── include_router(auth_router, prefix="/auth")
│           ├── include_router(users_router, prefix="/users")
│           └── lifespan: connect Redis, run DB migrations
│
├── auth/
│   ├── router.py
│   │     ├── POST /register  → auth_service.register(data)
│   │     ├── POST /login     → auth_service.login(data, response)
│   │     └── POST /logout    → auth_service.logout(session_id)
│   │
│   └── service.py
│         ├── register(data)
│         │     ├── repo.get_user_by_email(email)   → raise ConflictError if exists
│         │     ├── hash_password(data.password)
│         │     └── repo.create_user(...)           → return UserSchema
│         │
│         ├── login(data, response)
│         │     ├── repo.get_user_by_email(email)   → raise NotFoundError if not found
│         │     ├── verify_password(plain, hashed)  → raise AuthError if mismatch
│         │     ├── session_id = uuid4()
│         │     ├── cache.set_session(session_id, user.id)
│         │     └── response.set_cookie("session_id", session_id)
│         │
│         └── logout(session_id)
│               └── cache.delete_session(session_id)
│
├── users/
│   ├── router.py
│   │     └── GET /me  → Depends(get_current_user) → users_service.get_me(user_id)
│   │
│   └── service.py
│         └── get_me(user_id)
│               └── repo.get_user_by_id(user_id)   → return UserSchema
│
├── repository.py
│     ├── get_user_by_id(id)    → SELECT * FROM users WHERE id=$1
│     ├── get_user_by_email(e)  → SELECT * FROM users WHERE email=$1
│     └── create_user(data)     → INSERT INTO users ... RETURNING *
│
└── cache.py
      ├── set_session(sid, uid) → SETEX session:{sid} 86400 uid
      ├── get_session(sid)      → GET session:{sid}
      └── delete_session(sid)   → DEL session:{sid}
```

---

### 2.2 Video Service

```
app/
├── videos/
│   ├── router.py
│   │     ├── POST /upload   → Depends(auth) → video_service.upload(file, meta, user_id)
│   │     ├── GET  /:id      →                 video_service.get(video_id)
│   │     ├── GET  /         →                 video_service.list(page, limit, creator_id)
│   │     ├── PATCH /:id     → Depends(auth) → video_service.update(video_id, data, user_id)
│   │     └── GET  /:id/status →               video_service.get_status(video_id)
│   │
│   └── service.py
│         ├── upload(file, meta, user_id)
│         │     ├── video_id = uuid4()
│         │     ├── file_path = save_file(file, video_id)      ← writes to /media/uploads/
│         │     ├── repo.create_video(video_id, meta, user_id, file_path)
│         │     ├── kafka.publish("video.uploaded", video_id, payload)
│         │     └── return VideoSchema
│         │
│         ├── update(video_id, data, user_id)
│         │     ├── video = repo.get_video(video_id)           → 404 if not found
│         │     ├── if video.creator_id != user_id → raise ForbiddenError
│         │     └── repo.update_video(video_id, data)
│         │
│         └── update_status(video_id, status, extra_fields)   ← called by workers
│               └── repo.update_video_status(video_id, status, **extra_fields)
│
└── repository.py
      ├── create_video(...)
      ├── get_video(id)
      ├── list_videos(page, limit, creator_id)
      ├── update_video(id, **fields)
      └── update_video_status(id, status, **fields)
```

---

### 2.3 Heatmap Aggregator (Kafka Consumer, no HTTP)

```
app/
├── main.py
│     └── asyncio.run(start())
│           ├── await db.connect()
│           ├── await redis.connect()
│           ├── await kafka_producer.start()
│           ├── asyncio.create_task(consumer.consume())    ← main loop
│           └── asyncio.create_task(flusher.run_hourly())  ← background flush
│
├── consumer.py
│     └── consume()
│           └── async for msg in kafka_consumer:
│                 event = deserialize(msg.value)
│                 await aggregator.record_event(event)     ← hot path
│                 await viral_detector.check(event)        ← check after record
│
├── aggregator.py
│     └── record_event(event)
│           ├── seg_id = floor(event.videoTs / 5)
│           ├── live_key  = f"heatmap:{vid}:live:{seg_id}"
│           ├── total_key = f"heatmap:{vid}:total:{seg_id}"
│           ├── await redis.hincrby(live_key,  event.eventType, 1)
│           ├── await redis.expire(live_key, 600)
│           ├── await redis.hincrby(total_key, event.eventType, 1)
│           ├── await redis.expire(total_key, 604800)
│           └── await redis.publish(f"heatmap-updates:{vid}", payload)
│
├── viral_detector.py
│     └── check(event)
│           ├── total  = await redis.hget(total_key, "REWIND")
│           ├── mean, stddev = await redis.hmget(baseline_key, "mean", "stddev")
│           ├── sigma  = (total - mean) / stddev
│           └── if sigma > 3.0: await kafka.publish("heatmap-alerts", ...)
│
└── flusher.py
      └── run_hourly()
            └── while True:
                  await asyncio.sleep(3600)
                  video_ids = await scan_active_videos()
                  for vid in video_ids:
                      rows = await build_snapshot_rows(vid)
                      await repo.bulk_upsert_snapshots(rows)
```

---

### 2.4 Encoding Worker (Kafka Consumer, no HTTP)

```
app/
├── main.py
│     └── asyncio.run(consumer.consume())
│
├── consumer.py
│     └── consume()
│           └── async for msg in kafka_consumer:
│                 event = deserialize(msg.value)
│                 # Run blocking ffmpeg in thread executor
│                 loop = asyncio.get_event_loop()
│                 await loop.run_in_executor(None, process, event)
│
└── encoder.py
      └── process(event)
            ├── video_id   = event["videoId"]
            ├── input_path = event["filePath"]
            ├── update_status(video_id, "processing")      ← sync DB call
            ├── log_start(video_id)                        ← MongoDB
            ├── run_ffmpeg_hls(video_id, input_path)       ← blocking subprocess
            ├── duration = probe_duration(input_path)      ← ffmpeg probe
            ├── update_video(video_id, hls_path, duration, "ready")
            ├── publish_processed_event(video_id, ...)
            └── log_complete(video_id)                     ← MongoDB
```

---

## 3. Class Diagrams

### 3.1 Domain Models (Pydantic Schemas)

```
┌──────────────────────────────┐
│         UserBase             │
│──────────────────────────────│
│ + username : str             │
│ + email    : EmailStr        │
└──────────────┬───────────────┘
               │ extends
       ┌───────┴──────────┐
       │                  │
┌──────▼──────┐    ┌──────▼────────────┐
│ UserCreate  │    │  UserResponse     │
│─────────────│    │───────────────────│
│ + password  │    │ + id         : UUID│
│   : str     │    │ + created_at : dt │
└─────────────┘    └───────────────────┘

┌──────────────────────────────┐
│         VideoBase            │
│──────────────────────────────│
│ + title       : str          │
│ + description : str | None   │
└──────────────┬───────────────┘
               │ extends
       ┌───────┴──────────────────┐
       │                          │
┌──────▼──────────┐    ┌──────────▼──────────────────┐
│  VideoCreate    │    │      VideoResponse           │
│─────────────────│    │──────────────────────────────│
│ (no extra fields│    │ + id              : UUID     │
│  — file via     │    │ + creator_id      : UUID     │
│  multipart)     │    │ + hls_path        : str|None │
└─────────────────┘    │ + thumbnail_path  : str|None │
                       │ + duration        : float|None│
                       │ + status          : VideoStatus│
                       │ + created_at      : datetime  │
                       └──────────────────────────────┘

┌───────────────────────────────────────┐
│         InteractionEvent             │
│───────────────────────────────────────│
│ + videoId    : UUID                   │
│ + eventType  : EventType (Enum)       │
│ + videoTs    : float                  │
│ + seekFrom   : float | None           │
│ + clientTime : int                    │
└───────────────────────────────────────┘

EventType Enum:
  PLAY | PAUSE | REWIND | SEEK | SKIP | SPEED_CHANGE | BUFFER

VideoStatus Enum:
  uploading | processing | ready | failed
```

---

### 3.2 SQLAlchemy ORM Models

```
┌─────────────────────────────────────────┐
│           UserModel (ORM)               │
│─────────────────────────────────────────│
│ __tablename__ = "users"                 │
│                                         │
│ id            : UUID (PK)               │
│ username      : String(50)              │
│ email         : String(255)             │
│ password_hash : String(60)              │
│ created_at    : DateTime                │
│ updated_at    : DateTime                │
│                                         │
│ # Relationships                         │
│ videos        : List[VideoModel]        │◄──┐
│ watch_history : List[WatchHistoryModel] │   │
└─────────────────────────────────────────┘   │
                                              │ FK: creator_id
┌─────────────────────────────────────────┐   │
│           VideoModel (ORM)              │───┘
│─────────────────────────────────────────│
│ __tablename__ = "videos"                │
│                                         │
│ id              : UUID (PK)             │
│ creator_id      : UUID (FK → users)     │
│ title           : String(255)           │
│ description     : Text                  │
│ file_path       : Text                  │
│ hls_path        : Text (nullable)       │
│ thumbnail_path  : Text (nullable)       │
│ duration        : Numeric (nullable)    │
│ status          : Enum(VideoStatus)     │
│ file_size_bytes : BigInteger            │
│ mime_type       : String(50)            │
│ created_at      : DateTime              │
│ updated_at      : DateTime              │
│                                         │
│ # Relationships                         │
│ creator         : UserModel             │
│ summary         : VideoSummaryModel     │◄──┐
│ heatmap_snapshots: List[SnapshotModel]  │   │
└─────────────────────────────────────────┘   │
                                              │ FK: video_id
┌─────────────────────────────────────────┐   │
│       VideoSummaryModel (ORM)           │───┘
│─────────────────────────────────────────│
│ __tablename__ = "video_summaries"       │
│                                         │
│ id            : UUID (PK)               │
│ video_id      : UUID (FK → videos, UQ)  │
│ transcript    : Text                    │
│ summary       : Text                    │
│ key_moments   : JSON                    │
│ whisper_model : String(20)              │
│ processing_ms : Integer                 │
│ created_at    : DateTime                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│     VideoHeatmapSnapshotModel (ORM)     │
│─────────────────────────────────────────│
│ __tablename__ = "video_heatmap_snapshots│
│                                         │
│ id            : BigInteger (PK)         │
│ video_id      : UUID (FK → videos)      │
│ segment_id    : Integer                 │
│ segment_start : Numeric                 │
│ segment_end   : Numeric                 │
│ rewind_count  : Integer                 │
│ pause_count   : Integer                 │
│ seek_to_count : Integer                 │
│ skip_count    : Integer                 │
│ total_viewers : Integer                 │
│ snapshot_hour : DateTime                │
└─────────────────────────────────────────┘
```

---

### 3.3 Kafka Message Classes

```
┌────────────────────────────────────────┐
│         KafkaMessage (base)            │
│────────────────────────────────────────│
│ + topic      : str                     │
│ + key        : str   (partition key)   │
│ + value      : dict                    │
│ + produced_at: datetime                │
└────────────────┬───────────────────────┘
                 │ specializes
    ┌────────────┼────────────────────┐
    │            │                    │
┌───▼──────┐ ┌──▼──────────┐ ┌──────▼──────────────┐
│VideoUpload│ │VideoProcessed│ │ViewerInteractionEvent│
│──────────│ │─────────────│ │────────────────────  │
│videoId   │ │videoId      │ │videoId               │
│creatorId │ │creatorId    │ │userId (nullable)      │
│filePath  │ │hlsPath      │ │sessionId             │
│mimeType  │ │thumbnailPath│ │eventType             │
│title     │ │duration     │ │videoTs               │
└──────────┘ └─────────────┘ │seekFrom (nullable)   │
                              │clientTime            │
                              └──────────────────────┘
```

---

## 4. Sequence Diagrams

### 4.1 User Registration & Login

```
Browser         NGINX         User Service    PostgreSQL      Redis
   │               │               │               │             │
   │── POST /auth/register ────────▶               │             │
   │               │               │── SELECT user by email ────▶│
   │               │               │◀── (empty)    │             │
   │               │               │── bcrypt.hash(password)     │
   │               │               │── INSERT user ─────────────▶│
   │               │               │◀── UserModel  │             │
   │◀── 201 { id, username } ──────│               │             │
   │               │               │               │             │
   │── POST /auth/login ───────────▶               │             │
   │               │               │── SELECT user by email ────▶│
   │               │               │◀── UserModel  │             │
   │               │               │── bcrypt.verify(pw, hash)   │
   │               │               │── session_id = uuid4()      │
   │               │               │── SETEX session:{sid} ──────│────────────▶
   │               │               │   86400 user_id             │             │
   │◀── 200 Set-Cookie: session_id=<sid> ──────────│             │             │
```

---

### 4.2 Video Upload → Processing → Ready

```
Browser    NGINX    Video Svc    Kafka(video.uploaded)   Encoding Worker   Thumbnail Worker   PostgreSQL
   │          │         │                 │                     │                  │               │
   │─POST upload ───────▶                 │                     │                  │               │
   │          │         │─ save file ─────│─────────────────────│──────────────────│──────────────▶│(media vol)
   │          │         │─ INSERT video ──│─────────────────────│──────────────────│──────────────▶│ status=uploading
   │          │         │─ PRODUCE ───────▶                     │                  │               │
   │◀── 201 {id,status} ─│                │                     │                  │               │
   │          │         │                 │                     │                  │               │
   │          │         │                 │── CONSUME ──────────▶                  │               │
   │          │         │                 │── CONSUME ──────────│──────────────────▶               │
   │          │         │                 │                     │                  │               │
   │          │         │                 │            ffmpeg HLS│        ffmpeg thumb              │
   │          │         │                 │                     │─ UPDATE status ──│──────────────▶│ processing
   │          │         │                 │                     │─ UPDATE thumb ───│──────────────▶│ (thumbnail_path)
   │          │         │                 │                     │─ UPDATE hls,dur ─│──────────────▶│ status=ready
   │          │         │                 │─ PRODUCE video.processed ─────────────│               │
   │          │         │                 │                     │                  │               │
   │─ GET /videos/:id/status ──────────────▶                    │                  │               │
   │◀── { status: "ready" } ─────────────│                     │                  │               │
```

---

### 4.3 Video Streaming (HLS Playback)

```
Browser (hls.js)    NGINX     Streaming Service    Redis      media volume
       │               │              │               │              │
       │── GET /stream/{id}/index.m3u8 ───────────────▶              │
       │               │              │── GET stream:manifest:{id} ──▶
       │               │              │◀── (cache miss: nil)         │
       │               │              │── read file ─────────────────│──────────▶
       │               │              │◀── manifest text             │           │
       │               │              │── SETEX manifest {300} ──────▶           │
       │◀── 200 text/x-mpegurl ────────│              │              │           │
       │                               │              │              │           │
       │ (player parses, requests segs)│              │              │           │
       │── GET /stream/{id}/seg_000.ts ────────────────▶              │           │
       │               │              │── FileResponse(seg_000.ts) ──│──────────▶│
       │◀── 200 video/MP2T ────────────│              │              │           │
       │ (repeat for each segment)     │              │              │           │
```

---

### 4.4 Viewer Interaction Event → Heatmap Update

```
Browser   NGINX   Event Ingest   Kafka(viewer-events)  Aggregator   Redis   Heatmap API   Creator Dashboard
   │         │         │                  │                  │          │          │              │
   │─POST /events/interaction ────────────▶                  │          │          │              │
   │         │         │─ validate session │                  │          │          │              │
   │         │         │─ check rate limit │                  │          │          │              │
   │◀── 202 Accepted ──│                  │                  │          │          │              │
   │         │         │─ PRODUCE ─────────▶                  │          │          │              │
   │         │         │                  │── CONSUME ────────▶          │          │              │
   │         │         │                  │                  │─ HINCRBY ─▶          │              │
   │         │         │                  │                  │  live:28  │          │              │
   │         │         │                  │                  │─ PUBLISH heatmap-updates:{vid} ──────│
   │         │         │                  │                  │           │          │◀─ pub/sub ────│
   │         │         │                  │                  │           │          │─ SSE event ───▶
   │         │         │                  │                  │           │          │  {segId:28,   │
   │         │         │                  │                  │           │          │   REWIND:+1}  │
   │         │         │                  │                  │           │          │        [chart updates]
```

---

### 4.5 AI Summarization Pipeline

```
Kafka(video.processed)   Summarization Svc     media volume    PostgreSQL    Redis
          │                      │                   │              │           │
          │── CONSUME ───────────▶                   │              │           │
          │                      │── extract audio ──▶              │           │
          │                      │   ffmpeg .m3u8→.wav              │           │
          │                      │◀── audio.wav      │              │           │
          │                      │                   │              │           │
          │                      │ [run in executor]                │           │
          │                      │── whisper.transcribe(audio.wav)  │           │
          │                      │◀── {text, segments}              │           │
          │                      │                   │              │           │
          │                      │── bart.summarize(text)           │           │
          │                      │◀── summary_text   │              │           │
          │                      │                   │              │           │
          │                      │── extract_key_moments(segments)  │           │
          │                      │◀── [{timestamp, label}]          │           │
          │                      │                   │              │           │
          │                      │── INSERT video_summaries ────────▶           │
          │                      │── SET summary:{vid} ─────────────│───────────▶
```

---

### 4.6 Creator Dashboard — Full Heatmap Fetch + Live SSE

```
Creator Browser   NGINX   Heatmap API   Redis    PostgreSQL
      │              │         │           │           │
      │── GET /heatmap/{vid} ──▶           │           │
      │              │         │── HGETALL heatmap:{vid}:total:* ─▶
      │              │         │◀── all segment hashes              │
      │              │         │   (if keys expired → fallback)     │
      │              │         │── SELECT snapshots WHERE video_id=? ────────────▶
      │              │         │◀── snapshot rows                   │           │
      │◀── 200 { segments: [...] } ─────────│           │           │
      │              │         │           │           │           │
      │── GET /heatmap/{vid}/stream (SSE) ──▶           │           │
      │              │         │── SUBSCRIBE heatmap-updates:{vid} ─▶
      │              │         │                        │           │
      │  [viewer pauses somewhere, event flows through pipeline]    │
      │              │         │◀── PUBLISH {segId:28, REWIND:+1} ──│
      │              │         │── SSE: data: {segId:28,...}        │
      │◀── SSE event ──────────│           │           │           │
      │  [chart updates live]  │           │           │           │
```

---

## 5. API Contracts

### 5.1 Standard Response Envelope

All endpoints return a consistent JSON envelope:

```python
# schemas.py (shared)
class SuccessResponse(BaseModel, Generic[T]):
    data: T
    message: str = "success"

class ErrorResponse(BaseModel):
    error: str        # machine-readable code  e.g. "VIDEO_NOT_FOUND"
    message: str      # human-readable message e.g. "Video not found"
    detail: Any = None
```

Example success:
```json
{ "data": { "id": "uuid", "title": "..." }, "message": "success" }
```

Example error:
```json
{ "error": "VIDEO_NOT_FOUND", "message": "Video with id 'abc' not found", "detail": null }
```

---

### 5.2 All Endpoints Reference

#### User Service (`:8001`)

| Method | Path | Auth | Request Body | Response |
|---|---|---|---|---|
| POST | `/auth/register` | ❌ | `{username, email, password}` | `201 UserResponse` |
| POST | `/auth/login` | ❌ | `{email, password}` | `200 + Set-Cookie` |
| POST | `/auth/logout` | ✅ | — | `200 {message}` |
| GET | `/users/me` | ✅ | — | `200 UserResponse` |

#### Video Service (`:8002`)

| Method | Path | Auth | Request Body | Response |
|---|---|---|---|---|
| POST | `/videos/upload` | ✅ | `multipart: file, title, description` | `201 VideoResponse` |
| GET | `/videos/:id` | ❌ | — | `200 VideoResponse` |
| GET | `/videos` | ❌ | `?page=1&limit=20&creator_id=` | `200 PagedResponse<VideoResponse>` |
| PATCH | `/videos/:id` | ✅ | `{title?, description?}` | `200 VideoResponse` |
| GET | `/videos/:id/status` | ❌ | — | `200 {id, status}` |

#### Streaming Service (`:8003`)

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/stream/:id/index.m3u8` | ❌ | `200 text/x-mpegurl` |
| GET | `/stream/:id/:segment` | ❌ | `200 video/MP2T` |

#### Summarization Service (`:8004`)

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/summary/:id` | ❌ | `200 SummaryResponse` |

```json
// SummaryResponse
{
  "videoId": "uuid",
  "summary": "This video covers...",
  "keyMoments": [
    { "timestamp": 42.0, "label": "Introduction" }
  ],
  "transcriptAvailable": true
}
```

#### Trending Service (`:8005`)

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/trending` | ❌ | `200 TrendingResponse` |
| GET | `/recommendations/:userId` | ✅ | `200 List<VideoResponse>` |

#### Event Ingestion (`:8006`)

| Method | Path | Auth | Request Body | Response |
|---|---|---|---|---|
| POST | `/events/interaction` | ✅ | `InteractionEvent` | `202 Accepted` |

#### Heatmap API (`:8007`)

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/heatmap/:id` | ✅ (creator) | `200 HeatmapResponse` |
| GET | `/heatmap/:id/live` | ✅ (creator) | `200 HeatmapResponse` |
| GET | `/heatmap/:id/highlights` | ✅ (creator) | `200 HighlightsResponse` |
| SSE | `/heatmap/:id/stream` | ✅ (creator) | `text/event-stream` |

---

### 5.3 Pydantic Schema Definitions

```python
# ── User Schemas ───────────────────────────────────────────
class UserCreate(BaseModel):
    username : str = Field(min_length=3, max_length=50)
    email    : EmailStr
    password : str = Field(min_length=8, max_length=72)

class UserResponse(BaseModel):
    id         : UUID
    username   : str
    email      : EmailStr
    created_at : datetime
    model_config = ConfigDict(from_attributes=True)

# ── Video Schemas ──────────────────────────────────────────
class VideoStatus(str, Enum):
    uploading  = "uploading"
    processing = "processing"
    ready      = "ready"
    failed     = "failed"

class VideoResponse(BaseModel):
    id             : UUID
    creator_id     : UUID
    title          : str
    description    : str | None
    hls_path       : str | None
    thumbnail_path : str | None
    duration       : float | None
    status         : VideoStatus
    created_at     : datetime

# ── Interaction Event Schema ───────────────────────────────
class EventType(str, Enum):
    PLAY         = "PLAY"
    PAUSE        = "PAUSE"
    REWIND       = "REWIND"
    SEEK         = "SEEK"
    SKIP         = "SKIP"
    SPEED_CHANGE = "SPEED_CHANGE"
    BUFFER       = "BUFFER"

class InteractionEvent(BaseModel):
    videoId    : UUID
    eventType  : EventType
    videoTs    : float = Field(ge=0)
    seekFrom   : float | None = None
    clientTime : int

# ── Heatmap Schemas ────────────────────────────────────────
class SegmentCounts(BaseModel):
    REWIND : int = 0
    PAUSE  : int = 0
    SEEK   : int = 0
    SKIP   : int = 0
    PLAY   : int = 0

class HeatmapSegment(BaseModel):
    segmentId         : int
    start             : float
    end               : float
    counts            : SegmentCounts
    totalInteractions : int

class HeatmapResponse(BaseModel):
    videoId     : UUID
    segments    : list[HeatmapSegment]
    hotSegment  : HeatmapSegment | None
    coldSegment : HeatmapSegment | None

class Highlight(BaseModel):
    rank        : int
    segmentId   : int
    timestamp   : float
    rewindCount : int
    label       : str

class HighlightsResponse(BaseModel):
    videoId    : UUID
    highlights : list[Highlight]
```

---

## 6. Error Handling Strategy

### 6.1 Exception Hierarchy

```
Exception
└── AppException (base, HTTP-aware)
    ├── NotFoundError       → HTTP 404
    ├── ConflictError       → HTTP 409
    ├── AuthError           → HTTP 401
    ├── ForbiddenError      → HTTP 403
    ├── ValidationError     → HTTP 422
    ├── RateLimitError      → HTTP 429
    └── ServiceUnavailable  → HTTP 503
```

```python
# exceptions.py (each service)
class AppException(Exception):
    def __init__(self, error: str, message: str, status_code: int, detail=None):
        self.error       = error
        self.message     = message
        self.status_code = status_code
        self.detail      = detail

class NotFoundError(AppException):
    def __init__(self, resource: str, id: str):
        super().__init__(
            error=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} with id '{id}' not found",
            status_code=404
        )

class AuthError(AppException):
    def __init__(self, message="Invalid credentials"):
        super().__init__(error="UNAUTHORIZED", message=message, status_code=401)
```

### 6.2 Global Exception Handler (FastAPI)

```python
# main.py (each service)
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "message": exc.message, "detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_ERROR", "message": "Invalid input",
                 "detail": exc.errors()}
    )

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    # Log to MongoDB error_logs
    await error_logger.log(service_name, exc, request)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
    )
```

### 6.3 Kafka Consumer Error Handling

```python
# Pattern used in all Kafka consumers
async def safe_consume():
    async for msg in consumer:
        try:
            event = deserialize(msg.value)
            await process(event)
            # Offset committed ONLY after successful processing
        except KafkaProcessingError as e:
            await error_logger.log(service_name, e, context=msg.value)
            # Don't re-raise → continue consuming (skip poisoned message)
        except Exception as e:
            await error_logger.log(service_name, e, context=msg.value)
            # Critical error — don't commit offset → message redelivered
            raise
```

---

## 7. Design Patterns Used

### 7.1 Repository Pattern

Each service's database access is isolated in a `repository.py`. The service layer never writes raw SQL — it only calls repository methods.

```
Service Layer             Repository Layer          Database
─────────────             ─────────────────         ────────
video_service.get(id) → video_repo.find_by_id(id) → SELECT * FROM videos WHERE id=$1
```

**Why:** Swap PostgreSQL for another DB without touching business logic.

---

### 7.2 Cache-Aside Pattern

Used in Streaming Service and Heatmap API.

```python
async def get_data(key: str):
    # 1. Check cache
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)          # ← cache hit

    # 2. Cache miss — query source of truth
    data = await repository.fetch(key)
    if data is None:
        raise NotFoundError(...)

    # 3. Populate cache for next request
    await redis.setex(key, TTL, json.dumps(data))
    return data
```

---

### 7.3 Dependency Injection (FastAPI)

Auth, DB sessions, and Redis connections are provided via FastAPI `Depends()`:

```python
# dependencies.py
async def get_db() -> AsyncGenerator:
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
    await redis.expire(f"session:{session_id}", 86400)
    return user_id.decode()

# Usage in router:
@router.get("/users/me")
async def get_me(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    ...
```

---

### 7.4 Event-Driven Fan-Out

One Kafka event triggers multiple independent consumers (different consumer groups):

```
video.uploaded event
       │
       ├──▶ encoding-worker-group    → HLS encoding
       └──▶ thumbnail-worker-group   → Thumbnail generation

viewer-interaction-events
       │
       ├──▶ heatmap-aggregator-group → Redis counters + heatmap
       └──▶ trending-service-group   → Trending score update
```

**Why:** Decoupled — adding a new consumer (e.g., content moderation) requires zero changes to the producer.

---

### 7.5 Strangler Fig (Status Polling)

Video processing is long-running. Instead of holding the upload connection open, the client gets a `201` immediately and polls:

```
Client                         Server
  │── POST /videos/upload ──────▶
  │◀── 201 { id, status: "uploading" }
  │
  │ (polling loop)
  │── GET /videos/{id}/status ───▶
  │◀── { status: "processing" }
  │── GET /videos/{id}/status ───▶
  │◀── { status: "ready" }  ✅ done
```

---

### 7.6 Outbox-like Fire-and-Forget (Event Ingestion)

The event ingestion endpoint returns `202 Accepted` before the Kafka publish completes, using `BackgroundTasks`:

```python
@router.post("/events/interaction", status_code=202)
async def ingest_event(
    event: InteractionEvent,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    await check_rate_limit(user_id)
    background_tasks.add_task(kafka_producer.publish, event, user_id)
    return {"message": "accepted"}
```

---

## 8. Inter-Service Communication

### 8.1 Communication Matrix

```
┌──────────────────┬────────────────────┬────────────────┬─────────────┐
│ From             │ To                 │ Protocol       │ Sync/Async  │
├──────────────────┼────────────────────┼────────────────┼─────────────┤
│ Browser          │ Any Service        │ HTTP/REST      │ Sync        │
│ Browser          │ Heatmap API        │ SSE            │ Async push  │
│ Video Service    │ Processing Workers │ Kafka          │ Async       │
│ Encoding Worker  │ Summarization Svc  │ Kafka          │ Async       │
│ Event Ingestion  │ Aggregator         │ Kafka          │ Async       │
│ Event Ingestion  │ Trending Service   │ Kafka          │ Async       │
│ Aggregator       │ Heatmap API        │ Redis Pub/Sub  │ Async push  │
│ Aggregator       │ Kafka alerts topic │ Kafka          │ Async       │
│ Any Service      │ User Service       │ None (Redis)   │ Sync        │
│                  │ (session lookup)   │ (shared cache) │             │
└──────────────────┴────────────────────┴────────────────┴─────────────┘
```

> **Note:** Services do NOT call each other's HTTP APIs directly (no service-to-service REST). All cross-service coordination is via Kafka or shared Redis.

### 8.2 Why No Service-to-Service REST?

Direct REST between services creates tight coupling and cascading failures. Instead:
- **Kafka** for events (async, durable, decoupled)
- **Shared Redis** for fast ephemeral lookups (sessions, cache)
- **Shared PostgreSQL** for consistent persistent reads (videos metadata by streaming service)

---

## 9. Configuration Management

### 9.1 Pydantic BaseSettings Pattern (all services)

```python
# config.py (each service)
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    POSTGRES_HOST     : str = "localhost"
    POSTGRES_PORT     : int = 5432
    POSTGRES_USER     : str
    POSTGRES_PASSWORD : str
    POSTGRES_DB       : str

    # Redis
    REDIS_HOST : str = "localhost"
    REDIS_PORT : int = 6379

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS : str = "kafka:9092"

    # Service-specific
    SESSION_TTL_SECONDS : int = 86400    # User Service only
    SEGMENT_SIZE        : int = 5        # Heatmap Aggregator only
    WHISPER_MODEL       : str = "base"   # Summarization Service only

    @property
    def POSTGRES_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

All config is read from environment variables (injected by Docker Compose from `.env`). No secrets in code.

---

## 10. Security Design

### 10.1 Session Security

```
Session cookie properties:
  HttpOnly  = True   → JS cannot read it (XSS protection)
  SameSite  = Lax    → CSRF protection for cross-site requests
  Secure    = True   → HTTPS only (set in production)
  Path      = /      → Valid for all routes

Session validation on every protected request:
  1. Read session_id from cookie
  2. GET session:{session_id} from Redis
  3. If nil → 401 Unauthorized
  4. If found → reset TTL (sliding expiry)
  5. Return user_id for downstream use
```

### 10.2 Input Validation

All inputs validated by Pydantic before reaching the service layer:
- Email format validated via `EmailStr`
- Password length: min 8, max 72 (bcrypt limit)
- videoTs: `ge=0` (non-negative)
- EventType: strict Enum (no arbitrary strings accepted)

### 10.3 Authorization Checks

```python
# Creator-only operations (Video PATCH, Heatmap GET)
async def verify_ownership(video_id: UUID, user_id: str, repo):
    video = await repo.get_video(video_id)
    if video is None:
        raise NotFoundError("Video", str(video_id))
    if str(video.creator_id) != user_id:
        raise ForbiddenError("You are not the creator of this video")
    return video
```

### 10.4 Rate Limiting

```
Event Ingestion: 100 events/min per session (Redis token bucket)
Auth endpoints : 10 requests/min per IP (NGINX limit_req_zone)

# nginx.conf rate limiting
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
location /auth/ {
    limit_req zone=auth burst=5;
    proxy_pass http://user_service;
}
```

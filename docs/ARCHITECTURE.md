# Architecture — Distributed Video Streaming Platform

---

## System Architecture

```
╔══════════════════════════════════════════════════════════════════════════╗
║                        USER'S BROWSER / CLIENT                          ║
║                    React 18 + Vite · hls.js · recharts                  ║
╚══════════════════════════════════════╦═══════════════════════════════════╝
                                       ║  HTTP Requests
                                       ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                      NGINX  API GATEWAY  (port 80)                      ║
║              Routing  ·  Rate Limiting  ·  Static File Serving          ║
╚══╦════════╦════════╦════════╦════════╦════════╦════════╦════════════════╝
   ║        ║        ║        ║        ║        ║        ║
   ▼        ▼        ▼        ▼        ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│User  │ │Video │ │Stream│ │Summ. │ │Trend │ │Event │ │Heat  │
│Svc   │ │Svc   │ │Svc   │ │Svc   │ │Svc   │ │Ingest│ │API   │
│:8001 │ │:8002 │ │:8003 │ │:8004 │ │:8005 │ │:8006 │ │:8007 │
└──┬───┘ └──┬───┘ └──────┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
   │        │  video.uploaded  │        │         │  viewer │
   │        ╠══════════════════╬════════╬═════════╣ events  │
   │        ║                  ║        ║         ║         │
   │  ╔═════════════════════════════════════════════════╗   │
   │  ║           APACHE KAFKA EVENT BUS                ║   │
   │  ║  Topics:                                        ║   │
   │  ║   • video.uploaded          (3  partitions)     ║   │
   │  ║   • video.processed         (3  partitions)     ║   │
   │  ║   • viewer-interaction-events (12 partitions)   ║   │
   │  ║   • heatmap-aggregated      (6  partitions)     ║   │
   │  ║   • heatmap-alerts          (3  partitions)     ║   │
   │  ╚══════╦════════════╦══════════════╦══════════════╝   │
   │         ║            ║              ║                   │
   │         ▼            ▼              ▼                   │
   │    ┌─────────┐ ┌──────────┐ ┌──────────────┐          │
   │    │Encoding │ │Thumbnail │ │Heatmap       │          │
   │    │Worker   │ │Worker    │ │Aggregator    │          │
   │    │(no port)│ │(no port) │ │(no port)     │          │
   │    └────┬────┘ └──────────┘ └──────┬───────┘          │
   │         │ video.processed           │ heatmap-aggregated│
   │         ▼                           ╚══════════════════╝
   │    ┌──────────────┐
   │    │Summarization │
   │    │Service :8004 │
   │    └──────────────┘
   ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                           DATA STORES                                   ║
║  ┌──────────────────┐   ┌────────────────────┐   ┌──────────────────┐  ║
║  │  PostgreSQL :5432│   │   Redis :6379       │   │ MongoDB :27017   │  ║
║  │ • users          │   │ • session:{sid}     │   │ • processing_logs│  ║
║  │ • videos         │   │ • trending:videos   │   │ • error_logs     │  ║
║  │ • video_summaries│   │ • heatmap:{vid}:*   │   │ (TTL auto-rotate)│  ║
║  │ • watch_history  │   │ • summary:{vid}     │   └──────────────────┘  ║
║  │ • viewer_events  │   │ • stream:manifest:* │                         ║
║  │ • heatmap_snap.. │   │ • ratelimit:events:*│                         ║
║  │ • viral_alerts   │   └────────────────────┘                         ║
║  └──────────────────┘                                                   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Component Breakdown

### Microservices

| Service                   | Port | Status          | Responsibility                                   |
| ------------------------- | ---- | --------------- | ------------------------------------------------ |
| **user-service**          | 8001 | ✅ Implemented  | Register · login · session auth (Redis)          |
| **video-service**         | 8002 | ✅ Implemented  | Upload metadata · trigger Kafka `video.uploaded` |
| **shared**                | —    | ✅ Implemented  | Common deps, exceptions, response schemas        |
| **streaming-service**     | 8003 | 🔲 Planned      | Serve HLS manifests + `.ts` chunks from disk     |
| **summarization-service** | 8004 | 🔲 Planned      | Whisper transcription → BART summary → cache     |
| **trending-service**      | 8005 | 🔲 Planned      | ZINCRBY in Redis → leaderboard via ZREVRANGE     |
| **event-ingestion**       | 8006 | 🔲 Planned      | Accept viewer events (202 Accepted) → Kafka      |
| **heatmap-api**           | 8007 | 🔲 Planned      | Serve heatmap data · SSE live feed · highlights  |

### Background Workers (Kafka Consumers, no HTTP port)

| Worker                 | Status     | Consumes                    | Produces                               |
| ---------------------- | ---------- | --------------------------- | -------------------------------------- |
| **encoding-worker**    | 🔲 Planned | `video.uploaded`            | `video.processed`                      |
| **thumbnail-worker**   | 🔲 Planned | `video.uploaded`            | —                                      |
| **heatmap-aggregator** | 🔲 Planned | `viewer-interaction-events` | `heatmap-aggregated`, `heatmap-alerts` |

### Data Stores

| Store          | Purpose                                          | Why                                |
| -------------- | ------------------------------------------------ | ---------------------------------- |
| **PostgreSQL** | Users, videos, heatmaps, history                 | Relational, ACID transactions      |
| **Redis**      | Sessions, heatmap counters, trending sorted set  | Sub-millisecond reads; TTL support |
| **MongoDB**    | Processing logs, error logs                      | Flexible schema; TTL auto-rotation |

---

## 3-Layer Architecture Pattern

Every service follows a strict layered pattern (Django-inspired):

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — PRESENTATION                                 │
│  router.py  ·  schemas.py                               │
├─────────────────────────────────────────────────────────┤
│  LAYER 2 — BUSINESS LOGIC                               │
│  service.py                                             │
├─────────────────────────────────────────────────────────┤
│  LAYER 3 — DATA                                         │
│  model.py  ·  repository.py  ·  cache.py  ·  migrations/│
└─────────────────────────────────────────────────────────┘
```

**Rule:** Data flows downward only. Router → Service → Repository/Cache. Never the reverse.

### Internal Data Flow (HTTP Services)

```
HTTP Request
     │
     ▼
 router.py          ← validates input (Pydantic schemas), injects auth
     │
     ▼
 service.py         ← all business logic, raises domain exceptions
     │
     ├──────────────►  repository.py  ← SQLAlchemy queries only
     ├──────────────►  cache.py       ← Redis ops only
     └──────────────►  kafka_producer ← fire-and-forget events
          │
          ▼
     PostgreSQL / Redis / Kafka
```

### Layer Reference

| File                    | Layer              | Responsibility                          |
| ----------------------- | ------------------ | --------------------------------------- |
| `{domain}/router.py`   | L1 — Presentation  | HTTP routes, auth deps, call service    |
| `{domain}/schemas.py`  | L1 — Presentation  | Pydantic request/response models        |
| `{domain}/service.py`  | L2 — Business      | All business rules, no raw SQL          |
| `models.py`            | L3 — Data          | SQLAlchemy ORM models for this service  |
| `{domain}/repository.py` | L3 — Data        | DB queries only, returns domain objects |
| `{domain}/cache.py`    | L3 — Data          | Redis get/set/expire/incr only          |
| `config.py`            | Infrastructure     | Environment variables via Pydantic      |
| `database.py`          | Infrastructure     | SQLAlchemy engine + session             |

---

## Kafka Event Flows

```
Creator uploads video
   └─▶ video-service (stores metadata)
         └─▶ Kafka: video.uploaded
               ├─▶ encoding-worker (produces HLS files)
               │     └─▶ Kafka: video.processed
               │           └─▶ summarization-service (Whisper + BART)
               └─▶ thumbnail-worker (extracts thumbnail)

User watches video
   └─▶ event-ingestion (202 immediately, never blocks playback)
         └─▶ Kafka: viewer-interaction-events
               ├─▶ heatmap-aggregator (increments Redis counters)
               └─▶ trending-service (updates leaderboard)
```

---

## Folder Structure (Current)

Only `user-service`, `video-service`, and `shared` are implemented.

```
project/
├── docker-compose.yml
├── .env.example
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── shared/                     ← Python package shared by all services
│   │   ├── __init__.py
│   │   ├── dependencies.py         ← get_db(), get_redis(), get_current_user()
│   │   ├── exceptions.py           ← AppException base + standard HTTP errors
│   │   └── schemas.py              ← SuccessResponse[T], ErrorResponse, PagedResponse[T]
│   │
│   ├── user-service/               ← Port 8001
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   └── app/
│   │       ├── main.py             ← FastAPI app + lifespan + exception handlers
│   │       ├── config.py           ← Pydantic BaseSettings
│   │       ├── database.py         ← SQLAlchemy async engine + session
│   │       ├── redis_client.py     ← Async Redis singleton
│   │       ├── models.py           ← SQLAlchemy ORM models
│   │       ├── exceptions.py       ← EmailConflict, AuthError, UserNotFound
│   │       ├── auth/               ← POST /register, /login, /logout
│   │       │   ├── router.py
│   │       │   ├── schemas.py
│   │       │   ├── service.py
│   │       │   ├── repository.py
│   │       │   └── cache.py
│   │       └── users/              ← GET /me
│   │           ├── router.py
│   │           ├── schemas.py
│   │           ├── service.py
│   │           └── repository.py
│   │
│   └── video-service/              ← Port 8002
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── alembic.ini
│       ├── migrations/
│       └── app/
│           ├── main.py
│           ├── config.py
│           ├── database.py
│           ├── redis_client.py
│           ├── kafka_producer.py   ← Publishes to: video.uploaded
│           ├── models.py           ← Video SQLAlchemy model
│           ├── exceptions.py       ← VideoNotFound, ForbiddenAccess
│           ├── auth_utils.py
│           └── videos/             ← POST /upload, GET /{id}, GET /list, etc.
│               ├── router.py
│               ├── schemas.py
│               ├── service.py
│               ├── repository.py
│               └── cache.py
├── frontend/                       ← React 18 + Vite
└── docs/
```

---

## LLD: User Service (`:8001`)

### Module Design

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
│   └── service.py
│         ├── register(data)
│         │     ├── repo.get_user_by_email(email)   → raise ConflictError if exists
│         │     ├── hash_password(data.password)
│         │     └── repo.create_user(...)           → return UserSchema
│         ├── login(data, response)
│         │     ├── repo.get_user_by_email(email)   → raise NotFoundError
│         │     ├── verify_password(plain, hashed)  → raise AuthError
│         │     ├── session_id = uuid4()
│         │     ├── cache.set_session(session_id, user.id)
│         │     └── response.set_cookie("session_id", session_id)
│         └── logout(session_id)
│               └── cache.delete_session(session_id)
│
├── users/
│   ├── router.py
│   │     └── GET /me  → Depends(get_current_user) → users_service.get_me(user_id)
│   └── service.py
│         └── get_me(user_id) → repo.get_user_by_id(user_id)
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

### API Endpoints

| Method | Path             | Auth | Request Body                    | Response            |
| ------ | ---------------- | ---- | ------------------------------- | ------------------- |
| POST   | `/auth/register` | ❌   | `{username, email, password}`   | `201 UserResponse`  |
| POST   | `/auth/login`    | ❌   | `{email, password}`             | `200 + Set-Cookie`  |
| POST   | `/auth/logout`   | ✅   | —                               | `200 {message}`     |
| GET    | `/users/me`      | ✅   | —                               | `200 UserResponse`  |

### Schemas

```python
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
```

---

## LLD: Video Service (`:8002`)

### Module Design

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
│         │     ├── file_path = save_file(file, video_id)
│         │     ├── repo.create_video(video_id, meta, user_id, file_path)
│         │     ├── kafka.publish("video.uploaded", video_id, payload)
│         │     └── return VideoSchema
│         ├── update(video_id, data, user_id)
│         │     ├── video = repo.get_video(video_id)  → 404 if not found
│         │     ├── if video.creator_id != user_id → raise ForbiddenError
│         │     └── repo.update_video(video_id, data)
│         └── update_status(video_id, status, extra_fields)
│               └── repo.update_video_status(video_id, status, **extra_fields)
│
└── repository.py
      ├── create_video(...)
      ├── get_video(id)
      ├── list_videos(page, limit, creator_id)
      ├── update_video(id, **fields)
      └── update_video_status(id, status, **fields)
```

### API Endpoints

| Method | Path                | Auth | Request Body                          | Response                        |
| ------ | ------------------- | ---- | ------------------------------------- | ------------------------------- |
| POST   | `/videos/upload`    | ✅   | `multipart: file, title, description` | `201 VideoResponse`             |
| GET    | `/videos/:id`       | ❌   | —                                     | `200 VideoResponse`             |
| GET    | `/videos`           | ❌   | `?page=1&limit=20&creator_id=`        | `200 PagedResponse<Video>`      |
| PATCH  | `/videos/:id`       | ✅   | `{title?, description?}`              | `200 VideoResponse`             |
| GET    | `/videos/:id/status`| ❌   | —                                     | `200 {id, status}`              |

### Schemas

```python
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
```

---

## LLD: Shared Module

Mounted read-only into every service container.

| File              | Exports                                              |
| ----------------- | ---------------------------------------------------- |
| `dependencies.py` | `get_db()`, `get_redis()`, `get_current_user()`      |
| `exceptions.py`   | `AppException`, `NotFoundError`, `ConflictError`, `AuthError`, `ForbiddenError` |
| `schemas.py`      | `SuccessResponse[T]`, `ErrorResponse`, `PagedResponse[T]` |

### Auth Dependency

```python
async def get_current_user(request: Request, redis = Depends(get_redis)) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthError("Not authenticated")
    user_id = await redis.get(f"session:{session_id}")
    if not user_id:
        raise AuthError("Session expired")
    await redis.expire(f"session:{session_id}", 86400)  # sliding window
    return user_id.decode()
```

### Error Handling

```
Exception
└── AppException (base, HTTP-aware)
    ├── NotFoundError       → 404
    ├── ConflictError       → 409
    ├── AuthError           → 401
    ├── ForbiddenError      → 403
    ├── ValidationError     → 422
    ├── RateLimitError      → 429
    └── ServiceUnavailable  → 503
```

---

## End-to-End Flows

### Upload Flow

```
Creator → NGINX → video-service → PostgreSQL (metadata)
                               → Kafka: video.uploaded
                                     → encoding-worker → HLS files on disk
                                     │                 → Kafka: video.processed
                                     │                       → summarization-service
                                     └── thumbnail-worker → image on disk
```

### Watch Flow

```
Viewer → NGINX → streaming-service → Redis (manifest cache hit?)
                                   → disk (HLS .m3u8 + .ts chunks)
                                   → hls.js in browser (adaptive bitrate)
       → NGINX → heatmap-api → Redis (live heatmap counters) → overlay on player
```

### Auth Flow

```
Login → user-service → bcrypt verify → Redis: session:{sid} = userId (TTL 24h)
                                     → HttpOnly cookie: session_id
All protected routes → shared/dependencies.py → get_current_user → Redis lookup
```

---

## Key Design Decisions

| Decision                             | Reason                                                 |
| ------------------------------------ | ------------------------------------------------------ |
| **Session auth (not JWT)**           | Simpler revocation; Redis already in stack             |
| **No service-to-service REST calls** | Tight coupling avoided; Kafka + shared Redis instead   |
| **202 for viewer events**            | Viewer events must NEVER block video playback          |
| **HLS (not DASH)**                   | Better browser support with hls.js                     |
| **5-second heatmap buckets**         | Fine-grained insight without storage explosion         |
| **Redis sorted set for trending**    | `ZINCRBY` + `ZREVRANGE` = O(log N) leaderboard        |
| **Whisper `base` model**             | Runs on CPU; acceptable accuracy for a college project |
| **Docker Compose**                   | Single `docker-compose up` brings up all 16 containers |

---

## Inter-Service Communication

```
┌──────────────────┬────────────────────┬────────────────┬─────────────┐
│ From             │ To                 │ Protocol       │ Sync/Async  │
├──────────────────┼────────────────────┼────────────────┼─────────────┤
│ Browser          │ Any Service        │ HTTP/REST      │ Sync        │
│ Browser          │ Heatmap API        │ SSE            │ Async push  │
│ Video Service    │ Processing Workers │ Kafka          │ Async       │
│ Encoding Worker  │ Summarization Svc  │ Kafka          │ Async       │
│ Event Ingestion  │ Aggregator         │ Kafka          │ Async       │
│ Aggregator       │ Heatmap API        │ Redis Pub/Sub  │ Async push  │
│ Any Service      │ User Service       │ Shared Redis   │ Sync        │
│                  │ (session lookup)   │                │             │
└──────────────────┴────────────────────┴────────────────┴─────────────┘
```

> Services do **not** call each other's HTTP APIs directly. All cross-service coordination is via Kafka or shared Redis.

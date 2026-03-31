# 🤖 Copilot Implementation Reference

> **Read this file first at the start of every implementation session.**
> It contains all decisions, conventions, status, and pointers to detailed docs.

---

## 📌 Project Identity

| Field | Value |
|---|---|
| **Name** | Distributed Video Streaming Platform |
| **Type** | College project / full implementation |
| **Goal** | YouTube/Netflix-style platform with microservices, Kafka, Redis, async/sync patterns |
| **Unique Feature** | 🔥 Viewer Behavior Heatmap Engine |
| **Repo root** | `/home/kadam/PUCSD/sem-4/MWA/project` |

---

## 🗺️ Document Map

> Before implementing any phase, read the corresponding doc.

| Document | Path | Read When |
|---|---|---|
| This file | `docs/COPILOT.md` | Every session start |
| Project overview | `docs/intro.md` | First session only |
| **Unique feature** | `docs/unique-feature.md` | Phase 8 |
| **Database design** | `docs/database-design.md` | Any schema work |
| **LLD** | `docs/lld.md` | Any service work |
| **Shared patterns** | `docs/phases/shared-patterns.md` | Every service implementation |
| Phase index | `docs/phases/README.md` | Navigation |
| Phase 1 | `docs/phases/phase-1-infrastructure.md` | Implementing Phase 1 |
| Phase 2 | `docs/phases/phase-2-user-service.md` | Implementing Phase 2 |
| Phase 3 | `docs/phases/phase-3-video-service.md` | Implementing Phase 3 |
| Phase 4 | `docs/phases/phase-4-processing-pipeline.md` | Implementing Phase 4 |
| Phase 5 | `docs/phases/phase-5-streaming-service.md` | Implementing Phase 5 |
| Phase 6 | `docs/phases/phase-6-ai-summarization.md` | Implementing Phase 6 |
| Phase 7 | `docs/phases/phase-7-trending-recommendations.md` | Implementing Phase 7 |
| Phase 8 | `docs/phases/phase-8-heatmap-engine.md` | Implementing Phase 8 |
| Phase 9 | `docs/phases/phase-9-frontend.md` | Implementing Phase 9 |
| Phase 10 | `docs/phases/phase-10-integration.md` | Final integration |

---

## ✅ Implementation Status

> Update this table after completing each phase. Also update SQL todos.

| Phase | Description | Status | Notes |
|---|---|---|---|
| 1 | Infrastructure & Skeleton | ⬜ pending | Start here |
| 2 | User Service | ⬜ pending | Depends on 1 |
| 3 | Video Service | ⬜ pending | Depends on 1 |
| 4 | Processing Pipeline | ⬜ pending | Depends on 3 |
| 5 | Streaming Service | ⬜ pending | Depends on 4 |
| 6 | AI Summarization | ⬜ pending | Depends on 4 |
| 7 | Trending & Recommendations | ⬜ pending | Depends on 3 |
| 8a | Event Ingestion Service | ⬜ pending | Depends on 1 |
| 8b | Heatmap Aggregator | ⬜ pending | Depends on 8a |
| 8c | Heatmap API | ⬜ pending | Depends on 8b |
| 9 | Frontend (React.js) | ⬜ pending | Depends on 5,6,7,8c |
| 10 | Integration & Docs | ⬜ pending | Depends on 9 |

**Legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## 🛠️ Tech Stack (Confirmed)

| Layer | Technology | Notes |
|---|---|---|
| **Backend language** | Python 3.11 | All microservices |
| **Web framework** | FastAPI | All HTTP services |
| **Async runtime** | asyncio + uvicorn | All services |
| **Frontend** | React 18 + Vite | Single SPA |
| **Video player** | hls.js | In frontend |
| **Charts** | recharts | Heatmap dashboard |
| **API gateway** | NGINX | Routes + rate limiting |
| **Primary DB** | PostgreSQL 15 | Relational data |
| **Document store** | MongoDB 6 | Logs only |
| **Cache / sessions** | Redis 7 | Sessions, heatmap counters, trending |
| **Event streaming** | Apache Kafka (Confluent 7.5) | All async events |
| **Video processing** | ffmpeg | Encoding + thumbnails |
| **Transcription** | OpenAI Whisper (`base` model) | Local, CPU |
| **Summarization** | HuggingFace `facebook/bart-large-cnn` | Local, CPU |
| **Deployment** | Docker + Docker Compose | Single `docker-compose up` |
| **Auth** | Session-based (Redis) | HTTP-only cookie |
| **Migrations** | Alembic | Per-service, runs on startup |
| **Password hashing** | bcrypt | User service only |

---

## 🏗️ Final Folder Structure

```
project/
├── docker-compose.yml          ← brings up all 13 services + infra
├── .env                        ← secrets (gitignored)
├── .env.example                ← committed template
├── nginx/
│   └── nginx.conf
├── services/
│   ├── shared/                 ← Python package mounted into every service
│   │   ├── __init__.py
│   │   ├── dependencies.py     ← get_db, get_redis, get_current_user
│   │   ├── exceptions.py       ← AppException hierarchy
│   │   └── schemas.py          ← SuccessResponse[T], ErrorResponse, PagedResponse[T]
│   ├── user-service/           ← port 8001
│   ├── video-service/          ← port 8002
│   ├── encoding-worker/        ← no port (Kafka consumer)
│   ├── thumbnail-worker/       ← no port (Kafka consumer)
│   ├── streaming-service/      ← port 8003
│   ├── summarization-service/  ← port 8004
│   ├── trending-service/       ← port 8005
│   ├── event-ingestion/        ← port 8006
│   ├── heatmap-aggregator/     ← no port (Kafka consumer)
│   └── heatmap-api/            ← port 8007
├── frontend/                   ← React + Vite, port 3000
└── docs/                       ← all documentation
```

---

## 🔌 Service Port Map

| Service | Port | Type |
|---|---|---|
| NGINX (gateway) | 80 | HTTP |
| user-service | 8001 | FastAPI HTTP |
| video-service | 8002 | FastAPI HTTP |
| streaming-service | 8003 | FastAPI HTTP |
| summarization-service | 8004 | FastAPI HTTP |
| trending-service | 8005 | FastAPI HTTP |
| event-ingestion | 8006 | FastAPI HTTP |
| heatmap-api | 8007 | FastAPI HTTP + SSE |
| encoding-worker | — | Kafka consumer only |
| thumbnail-worker | — | Kafka consumer only |
| heatmap-aggregator | — | Kafka consumer only |
| frontend | 3000 | React (served by nginx) |
| PostgreSQL | 5432 | DB |
| MongoDB | 27017 | DB |
| Redis | 6379 | Cache |
| Kafka | 9092 | Event broker |
| Zookeeper | 2181 | Kafka coord |

---

## 📨 Kafka Topics

| Topic | Partitions | Key | Producer → Consumer(s) |
|---|---|---|---|
| `video.uploaded` | 3 | videoId | video-service → encoding-worker, thumbnail-worker |
| `video.processed` | 3 | videoId | encoding-worker → summarization-service |
| `viewer-interaction-events` | 12 | videoId | event-ingestion → heatmap-aggregator, trending-service |
| `heatmap-aggregated` | 6 | videoId | heatmap-aggregator → heatmap-api |
| `heatmap-alerts` | 3 | videoId | heatmap-aggregator → (notifications, future) |

---

## 🗄️ Database Ownership

> Each service OWNS its tables. Other services query shared tables via their own DB connection.

| PostgreSQL Table | Owner Service | Notes |
|---|---|---|
| `users` | user-service | Auth, profiles |
| `videos` | video-service | Metadata, lifecycle |
| `video_summaries` | summarization-service | AI output |
| `watch_history` | trending-service | Upserted on PLAY event |
| `viewer_events` | heatmap-aggregator | Partitioned by month |
| `video_heatmap_snapshots` | heatmap-aggregator | Hourly flush from Redis |
| `viral_segment_alerts` | heatmap-aggregator | Spike detection log |

| Redis Key Namespace | Owner Service |
|---|---|
| `session:{sid}` | user-service |
| `stream:manifest:{vid}` | streaming-service |
| `summary:{vid}` | summarization-service |
| `trending:videos` (sorted set) | trending-service |
| `heatmap:{vid}:live:{seg}` | heatmap-aggregator |
| `heatmap:{vid}:total:{seg}` | heatmap-aggregator |
| `heatmap:{vid}:baseline:{seg}` | heatmap-aggregator |
| `heatmap:{vid}:summary` | heatmap-api |
| `ratelimit:events:{sid}` | event-ingestion |

| MongoDB Collection | Owner |
|---|---|
| `processing_logs` | encoding-worker, thumbnail-worker |
| `error_logs` | all services |

---

## ⚙️ Non-Negotiable Conventions

> These apply to EVERY service. Never deviate.

### 1. Layered Architecture
```
router.py → service.py → repository.py + cache.py → DB/Redis
```
- Router: only HTTP + Pydantic validation + Depends()
- Service: all business logic, no raw SQL
- Repository: only SQLAlchemy queries, returns domain objects
- Cache: only Redis ops, returns None on miss

### 2. Every service folder must have:
```
app/
├── main.py          (lifespan hooks + 3 exception handlers)
├── config.py        (Pydantic BaseSettings + POSTGRES_URL property)
├── exceptions.py    (re-export AppException + service-specific)
├── logger.py        (MongoDB ErrorLogger instance)
└── {domain}/
    ├── router.py
    ├── service.py
    ├── repository.py
    └── cache.py
```

### 3. All endpoints return standard envelope
```json
{ "data": {...}, "message": "success" }           // success
{ "error": "CODE", "message": "...", "detail": null }  // error
```

### 4. Kafka producers always set partition key
```python
await producer.send(topic, key=entity_id.encode(), value=payload)
```

### 5. All Kafka consumers are idempotent
```python
if entity.status in ("ready", "failed"):
    return  # already processed — skip
```

### 6. Alembic runs before uvicorn
```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
```

### 7. Shared module is volume-mounted (never copied)
```yaml
volumes:
  - ./services/shared:/app/shared:ro
```

### 8. Session auth pattern (shared across all protected services)
- Cookie name: `session_id` (HttpOnly, SameSite=Lax)
- Redis key: `session:{session_id}` → `userId` (TTL 86400s, sliding)
- Dependency: `get_current_user` from `shared/dependencies.py`

### 9. Error codes (standard set)
| HTTP | Code | Trigger |
|---|---|---|
| 401 | `UNAUTHORIZED` | No/expired session |
| 403 | `FORBIDDEN` | Not resource owner |
| 404 | `{RESOURCE}_NOT_FOUND` | Entity missing |
| 409 | `CONFLICT` | Duplicate (email, etc.) |
| 422 | `VALIDATION_ERROR` | Pydantic failure |
| 429 | `RATE_LIMIT_EXCEEDED` | >100 events/min |
| 503 | `SERVICE_UNAVAILABLE` | Model/dep not ready |

### 10. CPU-heavy tasks run in executor
```python
# Whisper, BART, ffmpeg = blocking → must use executor
await asyncio.get_event_loop().run_in_executor(None, blocking_fn, arg)
```

---

## 🧩 Key Design Decisions (Why)

| Decision | Reason |
|---|---|
| Session-based auth (not JWT) | Chosen by developer; Redis stores sessions |
| No service-to-service REST | Avoid tight coupling; use Kafka + shared Redis |
| 202 Accepted for events | Viewer events must never block playback |
| Partition key = videoId | Ordered processing per video across all topics |
| 5-second heatmap buckets | Granular enough for insight, not too much storage |
| Whisper `base` model | Balance of speed vs accuracy on CPU |
| Redis for trending (sorted set) | Sub-ms ZINCRBY + ZREVRANGE for leaderboard |
| viewer_events partitioned by month | Enables fast partition DROP for data retention |
| MongoDB for logs only | TTL indexes for auto-rotation, flexible schema |
| HLS (not DASH) | Better browser compatibility with hls.js |

---

## 🔁 Dependency Order (Build Sequence)

```
Phase 1  ──────────────────────────────────────────────────────┐
   ├── Phase 2 (user-service)                                  │
   ├── Phase 3 (video-service) ──▶ Phase 4 (workers)          │
   │                                   ├──▶ Phase 5 (stream)  │
   │                                   └──▶ Phase 6 (AI)      │
   ├── Phase 7 (trending)                                      │
   └── Phase 8a (event-ingest) ──▶ Phase 8b ──▶ Phase 8c     │
                                                               │
   All of above ──────────────────▶ Phase 9 (frontend)        │
                                         └──▶ Phase 10        │
```

---

## 🧪 Tests (Required Phases Only)

| Service | Test File | Key Scenarios |
|---|---|---|
| user-service | `tests/test_auth.py` | register, login, logout, expired session, 409 duplicate |
| video-service | `tests/test_videos.py` | upload, 403 non-creator, status transitions, Kafka publish |
| event-ingestion | `tests/test_event_ingestion.py` | 202 immediate, rate limit 429, Kafka published |
| heatmap-aggregator | `tests/test_heatmap_aggregator.py` | segment bucketing, Redis INCR, viral alert |
| heatmap-api | `tests/test_heatmap_api.py` | fetch heatmap, 403 non-creator, highlights top 5 |

---

## 🌍 Environment Variables Reference

```env
# PostgreSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=videoplatform
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# MongoDB
MONGO_USER=admin
MONGO_PASSWORD=secret
MONGO_HOST=mongodb
MONGO_PORT=27017

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Session
SESSION_TTL_SECONDS=86400

# AI models
WHISPER_MODEL=base
HF_MODEL=facebook/bart-large-cnn

# Heatmap
SEGMENT_SIZE=5

# Service ports
USER_SERVICE_PORT=8001
VIDEO_SERVICE_PORT=8002
STREAMING_SERVICE_PORT=8003
SUMMARIZATION_SERVICE_PORT=8004
TRENDING_SERVICE_PORT=8005
EVENT_INGESTION_PORT=8006
HEATMAP_API_PORT=8007
```

---

## ▶️ How to Start a Session

1. Read this file (`docs/COPILOT.md`)
2. Check implementation status table above
3. Read the phase doc for the current phase
4. Read `docs/phases/shared-patterns.md` for patterns
5. Check relevant DB tables in `docs/database-design.md`
6. Check LLD section for the service in `docs/lld.md`
7. Update SQL todos: `UPDATE todos SET status='in_progress' WHERE id='phase-X'`
8. Implement — follow conventions above strictly
9. Run tests for the phase
10. Update status table in this file + SQL todos to `done`

---

## 📝 Session Notes

> Add notes here during implementation for next session context.

_No notes yet — implementation not started._

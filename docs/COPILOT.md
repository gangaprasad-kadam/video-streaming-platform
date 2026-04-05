# 🤖 Copilot Implementation Reference

> **Read this file first at the start of every implementation session.**
> It contains all decisions, conventions, status, and pointers to detailed docs.

---

## 🚀 Session Start Prompt

> **Copy-paste this at the start of every new Copilot session:**

```
Read docs/COPILOT.md in full.

Then follow the Session Protocol defined in it exactly:
- Check the implementation status table
- Ask me which phase to work on (show numbered options)
- Break the phase into individual features, ask which one to start
- Implement ONE feature at a time
- Write a test for it, run it, and confirm it passes before moving on
- After each feature, ask me: "Feature done. What next?" with options
- Never skip ahead or implement more than one feature at a time
- Update the status table after each completed phase

Begin now.
```

---

## 🔄 Session Protocol (Follow This Every Session)

> This is the law. Every session, every phase, every feature — follow this exactly.

### Step 1 — Orient
1. Read this file (`docs/COPILOT.md`) in full
2. Read the status table → identify what is `pending` and what is `in_progress`
3. Ask the user:

   > "Here is the current build status: [show table]
   > Which phase would you like to work on?
   > 1. Phase 1 — Infrastructure & Skeleton ⬜
   > 2. Phase 2 — User Service ⬜
   > ... (list all pending phases with their status icons)
   > Type the number or name."

### Step 2 — Select a Feature
Once a phase is chosen:
1. Read the phase doc (`docs/phases/phase-X-*.md`)
2. Break the phase into atomic features (each feature = one route, one worker function, one schema, etc.)
3. Ask the user:

   > "Phase X has these features to build:
   > 1. [Feature A]
   > 2. [Feature B]
   > 3. [Feature C]
   > Which one should we start with? (Recommended: 1)"

### Step 3 — Implement One Feature
1. State clearly: **"Building: [Feature Name]"**
2. Read the relevant sections from `docs/lld.md`, `docs/database-design.md`, `docs/phases/shared-patterns.md`
3. Implement the feature following conventions in this file
4. Show a summary of files created/changed

### Step 4 — Test Before Marking Done
1. Write the test (or show the test file location if it already exists)
2. Run the test
3. If test **passes** → announce: ✅ `[Feature Name]` complete
4. If test **fails** → fix the code, re-run, do NOT move on until green
5. Never mark a feature done without a passing test

### Step 5 — Ask What Next
After every completed feature, ask:

> "✅ [Feature Name] is done and tested.
> What would you like to do next?
> 1. Continue with next feature in this phase: [Feature B]
> 2. Switch to a different phase
> 3. Review what was built
> 4. Commit changes to git"

### Step 6 — Phase Complete
When all features in a phase are tested and done:
1. Update the status table in this file: `⬜ pending` → `✅ done`
2. Run the full test suite for the phase
3. Announce: **"Phase X complete. All tests passing."**
4. Ask the user which phase to tackle next

---

## ⚠️ Hard Rules (Never Break These)

| Rule | Detail |
|---|---|
| One feature at a time | Never implement Feature B while Feature A is untested |
| Test before done | A feature without a passing test is NOT done |
| Ask before proceeding | Always ask the user before moving to the next feature/phase |
| No silent assumptions | If something is unclear, ask with options — never guess |
| Show options | Always present numbered choices, not open-ended questions |
| Fix before move | If a test fails, fix it NOW — do not defer |

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
| **HLD (Architecture)** | `docs/HLD.md` | First session / any architecture question |
| **Project Overview** | `docs/PROJECT-OVERVIEW.md` | Client presentation / non-technical review |
| **Project Structure** | `docs/PROJECT-STRUCTURE.md` | Before implementing any service (canonical folder layout) |
| **Unique feature** | `docs/unique-feature.md` | Phase 8 |
| **Database design** | `docs/database-design.md` | Any schema work |
| **LLD** | `docs/lld.md` | Any service work |
| **Shared patterns** | `docs/phases/shared-patterns.md` | Every service implementation |
| **Phase tasks** | `docs/tasks/phase-X.md` | Before implementing any task in that phase |
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
| 1 | Infrastructure & Skeleton | ✅ done | Completed |
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

> Full detailed tree with all files → see `docs/PROJECT-STRUCTURE.md`

```
project/
├── docker-compose.yml          ← brings up all 16 containers with one command
├── .env                        ← secrets (gitignored)
├── .env.example                ← committed template
├── nginx/
│   └── nginx.conf              ← routing + rate limiting + static files
├── services/
│   ├── shared/                 ← Python package mounted (read-only) into every service
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
├── frontend/                   ← React 18 + Vite, port 3000
└── docs/                       ← all documentation
    ├── COPILOT.md              ← this file (AI session reference)
    ├── HLD.md                  ← high-level architecture
    ├── lld.md                  ← low-level design per service
    ├── database-design.md      ← full schema + ER diagram
    ├── unique-feature.md       ← heatmap engine deep-dive
    ├── PROJECT-OVERVIEW.md     ← non-technical overview (client-facing)
    ├── PROJECT-STRUCTURE.md    ← CANONICAL folder layout for all services
    ├── phases/                 ← per-phase implementation guides
    ├── tasks/                  ← per-phase task checklists
    └── diagrams/               ← architecture diagrams (PNG + Mermaid)
```

**Per-service internal structure** (applies to every service — see `docs/PROJECT-STRUCTURE.md`):
```
services/{service-name}/
├── Dockerfile
├── requirements.txt
├── alembic.ini + migrations/   ← (if service has a DB)
└── app/
    ├── main.py                 ← FastAPI app factory + lifespan
    ├── config.py               ← Pydantic BaseSettings
    ├── database.py             ← SQLAlchemy engine (if DB)
    ├── redis_client.py         ← Redis connection (if Redis)
    ├── kafka_producer.py       ← (if publishes events)
    ├── kafka_consumer.py       ← (if consumes events)
    ├── models.py               ← ALL SQLAlchemy ORM models [L3]
    ├── exceptions.py           ← service-specific exceptions
    └── {domain}/               ← one folder per business domain
        ├── __init__.py
        ├── router.py           ← HTTP routes + auth [L1]
        ├── schemas.py          ← Pydantic request/response [L1]
        ├── service.py          ← business logic [L2]
        ├── repository.py       ← DB queries only [L3]
        └── cache.py            ← Redis ops only [L3]
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
services/{service-name}/
├── Dockerfile
├── requirements.txt
├── alembic.ini          (if service has a DB)
├── migrations/          (if service has a DB)
│   ├── env.py
│   └── versions/
└── app/
    ├── main.py          (lifespan hooks + 3 exception handlers)
    ├── config.py        (Pydantic BaseSettings + POSTGRES_URL property)
    ├── database.py      (SQLAlchemy async engine — only if DB is used)
    ├── redis_client.py  (async Redis connection — only if Redis is used)
    ├── kafka_producer.py (only if service publishes events)
    ├── kafka_consumer.py (only if service consumes events)
    ├── models.py        (ALL SQLAlchemy ORM models for this service)
    ├── exceptions.py    (re-export AppException + service-specific)
    └── {domain}/
        ├── __init__.py
        ├── router.py    (HTTP routes + Depends() + call service only)
        ├── schemas.py   (Pydantic request/response models)
        ├── service.py   (all business logic)
        ├── repository.py (SQLAlchemy queries only — if DB used)
        └── cache.py     (Redis ops only — if Redis used)
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
| streaming-service | `tests/test_streaming.py` | manifest cache, segment validation, 404 not ready, Accept-Ranges |
| summarization-service | `tests/test_summarization.py` | Whisper+BART pipeline, chunking >1024 tokens, Kafka consumer, 404 |
| trending-service | `tests/test_trending.py` | ZINCRBY scoring, decay, watch_history upsert, recommendations, PLAY consumer |
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

1. Copy the **Session Start Prompt** (top of this file) and paste it into Copilot
2. Copilot will read this file, show you the status table, and ask which phase to work on
3. Pick a phase → pick a feature → it will implement + test it → ask what's next
4. Repeat until the project is complete

---

## 📝 Session Notes

> Add notes here during implementation for next session context.

_No notes yet — implementation not started._

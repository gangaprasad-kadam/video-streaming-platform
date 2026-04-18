# 🗺️ Project Roadmap — Distributed Video Streaming Platform

**Stack:** Python (FastAPI) · React.js · Docker Compose · Kafka · Redis · PostgreSQL · MongoDB
**Auth:** Session-based (Redis) · **AI:** Whisper + HuggingFace BART
**Unique Feature:** 🔥 Viewer Behavior Heatmap Engine

---

## Status Overview

| # | Phase | Status | Services |
|---|-------|--------|----------|
| 1 | Infrastructure & Skeleton | ✅ Done | — (Docker, Kafka, Redis, PostgreSQL, NGINX) |
| 2 | User Service | ✅ Done | `user-service` |
| 3 | Video Service | ✅ Done | `video-service` |
| 4 | Processing Pipeline | ✅ Done | `encoding-worker`, `thumbnail-worker` |
| 5 | Streaming Service | ✅ Done | `streaming-service` |
| 6 | AI Summarization | 🔲 Not Started | `summarization-service` |
| 7 | Trending & Recommendations | 🔲 Not Started | `trending-service` |
| 8 | Heatmap Engine ⭐ | 🔲 Not Started | `event-ingestion`, `heatmap-aggregator`, `heatmap-api` |
| 9 | Frontend | 🔲 Not Started | `frontend` |
| 10 | Integration & Docs | 🔲 Not Started | — (E2E testing, final compose) |

**Progress: 5 / 10 phases complete**

---

## Dependency Graph

```
Phase 1 (Infrastructure)
    ├── Phase 2 (User Service)
    ├── Phase 3 (Video Service)
    │       └── Phase 4 (Processing Pipeline)
    │               ├── Phase 5 (Streaming Service)
    │               └── Phase 6 (AI Summarization)
    ├── Phase 7 (Trending)
    └── Phase 8a (Event Ingestion)
            └── Phase 8b (Aggregator)
                    └── Phase 8c (Heatmap API)
                                    │
                    Phase 5 ────────┤
                    Phase 6 ────────┤──▶ Phase 9 (Frontend)
                    Phase 7 ────────┤                │
                    Phase 8c ───────┘                ▼
                                             Phase 10 (Integration)
```

**Next buildable phases** (all dependencies met): **Phase 4**, **Phase 7**, **Phase 8a**

---

## Phase Details

### Phase 1 — Infrastructure & Skeleton ✅ DONE

**What it builds:** Docker Compose environment with all shared infrastructure (PostgreSQL, MongoDB, Redis, Kafka, NGINX gateway) and the `services/shared/` Python module.

**Key deliverables:**
- `docker-compose.yml` with 6 infra services + health checks
- NGINX reverse proxy with route-based upstream mapping
- Kafka topic pre-creation via init container (5 topics)
- `.env.example` with all config variables
- `services/shared/` — dependencies, exceptions, response schemas

**Dependencies:** None
**Tech:** Docker Compose, PostgreSQL 15, MongoDB 6, Redis 7, Kafka (Confluent 7.5), NGINX

---

### Phase 2 — User Service ✅ DONE

**What it builds:** FastAPI microservice for user registration, login/logout, and profile retrieval with bcrypt password hashing and Redis session storage.

**Key deliverables:**
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`
- `GET /users/me` (session-authenticated)
- PostgreSQL `users` table with Alembic migrations
- Redis session store (`session:{sessionId}`, 24h sliding TTL)
- HttpOnly cookie-based auth (no JWT)

**Dependencies:** Phase 1
**Tech:** FastAPI, PostgreSQL, Redis, bcrypt, Pydantic, Alembic

---

### Phase 3 — Video Service ✅ DONE

**What it builds:** FastAPI microservice for video upload, metadata CRUD, and lifecycle management. Saves files to a shared Docker volume and publishes `video.uploaded` Kafka events.

**Key deliverables:**
- `POST /videos/upload` (multipart), `GET /videos/:id`, `GET /videos`, `PATCH /videos/:id`
- `GET /videos/:id/status` (polling endpoint for upload progress)
- PostgreSQL `videos` table with status lifecycle (`uploading → processing → ready | failed`)
- Kafka producer → `video.uploaded` topic
- Shared `media_volume` for file storage

**Dependencies:** Phase 1, Phase 2 (for auth)
**Tech:** FastAPI, PostgreSQL, aiokafka, aiofiles, python-multipart

---

### Phase 4 — Processing Pipeline 🔲 NOT STARTED

**What it builds:** Two Kafka consumer workers that auto-trigger on video upload — the Encoding Worker transcodes to HLS via ffmpeg, and the Thumbnail Worker extracts a JPEG frame. No HTTP API.

**Key deliverables:**
- `encoding-worker`: Kafka consumer (`video.uploaded`) → ffmpeg HLS transcoding → publishes `video.processed`
- `thumbnail-worker`: Kafka consumer (`video.uploaded`) → ffmpeg frame extraction at t=5s
- Duration calculation via ffprobe
- MongoDB `processing_logs` for audit trail
- Idempotent consumers (skip if already `ready`/`failed`)

**Dependencies:** Phase 3 (produces `video.uploaded` events)
**Tech:** aiokafka, ffmpeg, ffprobe, subprocess, Motor (MongoDB)

---

### Phase 5 — Streaming Service 🔲 NOT STARTED

**What it builds:** FastAPI service that serves HLS video segments to the browser. Caches the `.m3u8` manifest in Redis; serves `.ts` segments directly from disk.

**Key deliverables:**
- `GET /stream/:videoId/index.m3u8` (manifest, Redis-cached 5min)
- `GET /stream/:videoId/:segment.ts` (binary stream with range support)
- DB validation: only serves videos with `status = ready`
- Cache invalidation support for re-encoded videos

**Dependencies:** Phase 4 (HLS files must exist on volume)
**Tech:** FastAPI, Redis, FileResponse, aiofiles

---

### Phase 6 — AI Summarization 🔲 NOT STARTED

**What it builds:** Kafka consumer + HTTP API that transcribes video audio with Whisper, summarizes with BART, extracts key timestamps, and caches results.

**Key deliverables:**
- Kafka consumer (`video.processed`) → Whisper transcription → BART summarization
- `GET /summary/:videoId` (cache-aside: Redis 1h → PostgreSQL fallback)
- PostgreSQL `video_summaries` table (transcript, summary, key_moments JSONB)
- CPU-heavy AI calls run in thread executor to avoid blocking event loop
- Models pre-downloaded at Docker build time

**Dependencies:** Phase 4 (produces `video.processed` events)
**Tech:** OpenAI Whisper, HuggingFace Transformers (BART), ffmpeg, aiokafka

---

### Phase 7 — Trending & Recommendations 🔲 NOT STARTED

**What it builds:** Real-time trending leaderboard using Redis sorted sets, driven by viewer interaction events from Kafka. Includes basic hybrid recommendations (trending + watch history).

**Key deliverables:**
- Kafka consumer (`viewer-interaction-events`) → Redis `ZINCRBY` scoring
- `GET /trending` (top N from Redis sorted set, sub-ms reads)
- `GET /recommendations/:userId` (60% trending + 40% creator-based, minus watched)
- Score decay: hourly 0.9× multiplier background task
- PostgreSQL `watch_history` table (upserted on `PLAY` events)

**Dependencies:** Phase 1 (Kafka + Redis)
**Tech:** FastAPI, Redis sorted sets, aiokafka, PostgreSQL

---

### Phase 8 — Heatmap Engine ⭐ 🔲 NOT STARTED

The project's **unique feature** — three sub-components:

#### 8a — Event Ingestion
**What it builds:** Accepts viewer micro-interactions (pause, rewind, seek, skip) and publishes to Kafka. Returns `202 Accepted` immediately via `BackgroundTasks`.

**Key deliverables:**
- `POST /events/interaction` → 202 + async Kafka publish
- Redis token-bucket rate limiting (100 events/min per session)

**Dependencies:** Phase 1
**Tech:** FastAPI, aiokafka, Redis

#### 8b — Heatmap Aggregator
**What it builds:** Kafka consumer that buckets events into 5-second segments, maintains live + all-time Redis counters, detects viral segments (σ > 3), and flushes snapshots to PostgreSQL hourly.

**Key deliverables:**
- Segment bucketing (`videoTs ÷ 5s = segmentId`)
- Redis counters: `heatmap:{vid}:live:{seg}` (10min TTL) + `heatmap:{vid}:total:{seg}` (7d TTL)
- Redis pub/sub → `heatmap-updates:{videoId}` for SSE
- Viral detection → `heatmap-alerts` Kafka topic + `viral_segment_alerts` DB table
- Weekly baseline recalculation from `viewer_events` table

**Dependencies:** Phase 8a
**Tech:** aiokafka, Redis (HINCRBY, PUBLISH), PostgreSQL, Motor

#### 8c — Heatmap API
**What it builds:** REST + SSE endpoints for the creator dashboard. Reads heatmap data from Redis (fallback PostgreSQL) and streams live updates.

**Key deliverables:**
- `GET /heatmap/:videoId` (full heatmap with hot/cold segments)
- `GET /heatmap/:videoId/live` (5-minute window)
- `GET /heatmap/:videoId/highlights` (top 5 rewatched)
- `SSE /heatmap/:videoId/stream` (real-time push via Redis pub/sub)
- Creator-only access (403 for non-creators)

**Dependencies:** Phase 8b
**Tech:** FastAPI, Redis pub/sub, SSE (StreamingResponse), PostgreSQL

---

### Phase 9 — Frontend 🔲 NOT STARTED

**What it builds:** React SPA with auth, video browsing, HLS playback (hls.js), upload with status polling, and a creator dashboard with live heatmap visualization (recharts).

**Key deliverables:**
- Pages: Login, Register, Home (trending grid), Video Player, Upload, Dashboard, Browse
- HLS video player with hls.js + interaction event tracking (batched every 3s)
- Creator dashboard with live heatmap bar chart (recharts + SSE)
- AI summary + key moments display on player page
- Axios client with `withCredentials: true` and `SuccessResponse` envelope unwrapping

**Dependencies:** Phase 5, Phase 6, Phase 7, Phase 8c
**Tech:** React 18, Vite, hls.js, recharts, axios, react-router-dom v6

---

### Phase 10 — Integration & Documentation 🔲 NOT STARTED

**What it builds:** Final `docker-compose.yml` wiring all 13 services, end-to-end smoke tests, and submission-ready documentation.

**Key deliverables:**
- Complete docker-compose.yml (13 services + 3 volumes)
- 10-step E2E smoke test script (register → upload → process → stream → heatmap)
- Auth error testing (401 unauthenticated, 403 non-creator)
- Final documentation pass
- Submission checklist

**Dependencies:** All previous phases
**Tech:** Docker Compose, curl, bash

---

## Shared Patterns (All Services)

### 3-Layer Architecture

```
Layer 1 — Presentation   router.py + schemas.py    (HTTP routes, Pydantic validation)
Layer 2 — Business Logic service.py                (orchestration, business rules)
Layer 3 — Data           repository.py + cache.py  (DB queries, Redis operations)
```

No layer skipping: Router → Service → Repository/Cache.

### Standard Service Structure

```
services/{name}/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py          ← lifespan hooks, exception handlers
│   ├── config.py        ← Pydantic BaseSettings
│   ├── database.py      ← SQLAlchemy async engine
│   ├── redis_client.py
│   ├── models.py        ← ORM models (service-wide)
│   └── {domain}/
│       ├── router.py, service.py, repository.py, cache.py, schemas.py
└── tests/
```

### Key Conventions

- **Response envelope:** `SuccessResponse[T]` / `ErrorResponse` / `PagedResponse[T]` from `shared/schemas.py`
- **Exceptions:** `AppException` hierarchy — `NotFoundError`, `AuthError`, `ForbiddenError`, `ConflictError`, `RateLimitError`
- **Kafka keys:** Always `key=entity_id.encode()` for partition ordering
- **Idempotent consumers:** Check state before processing (handle Kafka redelivery)
- **Error logging:** All unhandled exceptions → MongoDB `error_logs` via Motor
- **Migrations:** Alembic `upgrade head` runs at container startup before uvicorn
- **Config:** `pydantic-settings` BaseSettings with `.env` file support

---

## Recommended Build Order

Based on dependency graph and parallel opportunities:

```
Already done:  Phase 1 → Phase 2 → Phase 3

Next sprint:   Phase 4  (Processing Pipeline)     ← unblocks 5, 6
               Phase 7  (Trending)                 ← independent, can parallel
               Phase 8a (Event Ingestion)           ← independent, can parallel

Then:          Phase 5  (Streaming)                ← needs 4
               Phase 6  (AI Summarization)          ← needs 4
               Phase 8b (Aggregator)                ← needs 8a
                 └── Phase 8c (Heatmap API)         ← needs 8b

Finally:       Phase 9  (Frontend)                 ← needs 5, 6, 7, 8c
               Phase 10 (Integration)              ← needs everything
```

---

## Folder Structure (Final)

```
project/
├── docker-compose.yml
├── .env.example
├── nginx/
│   └── nginx.conf
├── services/
│   ├── shared/                ← shared Python module (mounted into all services)
│   ├── user-service/          ← Phase 2 ✅
│   ├── video-service/         ← Phase 3 ✅
│   ├── encoding-worker/       ← Phase 4
│   ├── thumbnail-worker/      ← Phase 4
│   ├── streaming-service/     ← Phase 5
│   ├── summarization-service/ ← Phase 6
│   ├── trending-service/      ← Phase 7
│   ├── event-ingestion/       ← Phase 8a
│   ├── heatmap-aggregator/    ← Phase 8b
│   └── heatmap-api/           ← Phase 8c
├── frontend/                  ← Phase 9
└── docs/
    ├── ROADMAP.md             ← you are here
    ├── intro.md
    ├── unique-feature.md
    └── phases/                ← detailed phase guides
```

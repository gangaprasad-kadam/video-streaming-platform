# Distributed Video Streaming Platform

A scalable distributed video streaming platform (YouTube/Netflix-style) built with microservices, event-driven architecture, and real-time analytics.

**Progress: 10 / 12 Services Complete** (Frontend + Integration remaining)

---

## 🚀 Quick Start

```bash
# 1. Copy env file
cp .env.example .env

# 2. Start everything
./start.sh

# 3. Stop everything
./start.sh down
```

**API Endpoints** (via NGINX on port 80):

| Route | Service | Swagger Docs |
|-------|---------|--------------|
| `/auth/*`, `/users/*` | user-service | http://localhost:8001/docs |
| `/videos/*` | video-service | http://localhost:8002/docs |
| `/stream/*` | streaming-service | http://localhost:8003/docs |
| `/summary/*` | summarization-service | http://localhost:8004/docs |
| `/trending/*`, `/recommendations/*` | trending-service | http://localhost:8005/docs |
| `/events/*` | event-ingestion | http://localhost:8006/docs |
| `/heatmap/*` | heatmap-api | http://localhost:8008/docs |

---

## 🏗️ Architecture

```
Browser → NGINX (port 80) → Microservices → Data Stores
                                  ↕
                            Apache Kafka
                                  ↕
                     Background Workers (encoding, thumbnail)
```

| Service | Port | Responsibility |
|---------|------|----------------|
| user-service | 8001 | Registration, login, session auth (Redis) |
| video-service | 8002 | Video upload, metadata CRUD, Kafka events |
| encoding-worker | — | Consumes `video.uploaded` → FFmpeg HLS transcode → publishes `video.processed` |
| thumbnail-worker | — | Consumes `video.uploaded` → FFmpeg thumbnail extraction |
| streaming-service | 8003 | HLS manifest & segment delivery |
| summarization-service | 8004 | Consumes `video.processed` → Whisper transcription → DistilBART summary |
| trending-service | 8005 | Consumes viewer interactions → Redis sorted set leaderboard + recommendations |
| event-ingestion | 8006 | `POST /events/interaction` → validate + rate limit + Kafka publish (202) |
| heatmap-aggregator | 8007 | Consumes viewer interactions → 5s bucket scoring → Redis + MongoDB |
| heatmap-api | 8008 | `GET /heatmap/{id}` all-time, `/live` 5-min window, `/highlights` top segments |
| shared/ | — | Common exceptions, response schemas, auth dependencies |

**Data Stores:** PostgreSQL (relational data), Redis (sessions & cache), MongoDB (heatmap bucket data; error logs planned), Kafka (async event bus)

---

## 📂 Project Structure

```
project/
├── docker-compose.yml
├── .env / .env.example
├── start.sh
├── nginx/
│   └── nginx.conf
├── services/
│   ├── shared/                      ← common Python module (mounted into all services)
│   │   ├── exceptions.py            ← AppException hierarchy (NotFound, Auth, Conflict…)
│   │   ├── schemas.py               ← SuccessResponse[T], PagedResponse[T], ErrorResponse
│   │   └── dependencies.py          ← get_current_user (session cookie → Redis → user_id)
│   ├── user-service/                ← :8001 auth, sessions
│   ├── video-service/               ← :8002 upload, metadata CRUD
│   ├── encoding-worker/             ← Kafka consumer → FFmpeg HLS transcode
│   ├── thumbnail-worker/            ← Kafka consumer → FFmpeg thumbnail
│   ├── streaming-service/           ← :8003 HLS segment delivery
│   ├── summarization-service/       ← :8004 Whisper + DistilBART
│   ├── trending-service/            ← :8005 leaderboard + recommendations
│   ├── event-ingestion/             ← :8006 POST /events/interaction → Kafka
│   ├── heatmap-aggregator/          ← :8007 Kafka consumer → Redis + MongoDB bucket scoring
│   └── heatmap-api/                 ← :8008 GET /heatmap/{id} all-time / live / highlights
└── docs/
    ├── ARCHITECTURE.md              ← system design & LLD
    ├── DATABASE.md                  ← schemas (PostgreSQL, Redis, Kafka)
    ├── HEATMAP.md                   ← heatmap engine design & scoring spec
    ├── ROADMAP.md                   ← all build phases & status
    ├── diagrams/                    ← architecture diagrams (PNG)
    ├── service-working/             ← per-service technical reference (01–10)
    └── test/                        ← per-service Postman testing guides (01–09)
```

---

## 🏛️ Service Structure (user-service as example)

Every service follows the same **three-layer architecture**. Below is `user-service` laid out in full:

```
services/user-service/
├── Dockerfile
├── requirements.txt
├── alembic.ini                          ← Alembic config for DB migrations
├── pytest.ini
│
├── app/
│   ├── main.py                          ← FastAPI app, lifespan hooks, exception handlers
│   ├── config.py                        ← pydantic-settings BaseSettings (DATABASE_URL, REDIS_URL…)
│   ├── database.py                      ← SQLAlchemy async engine + Base + get_db dependency
│   ├── redis_client.py                  ← Redis singleton + get_redis dependency
│   ├── models.py                        ← SQLAlchemy ORM models (User table)
│   ├── exceptions.py                    ← service-specific exceptions (extends shared/)
│   │
│   ├── auth/                            ← domain: registration & login
│   │   ├── handler/
│   │   │   └── router.py               ← LAYER 1: HTTP routes (POST /auth/register, /login, /logout)
│   │   ├── utils/
│   │   │   ├── service.py              ← LAYER 2: business logic (bcrypt hash, session create/delete)
│   │   │   ├── schemas.py              ← Pydantic request/response models (RegisterRequest, LoginRequest…)
│   │   │   └── cache.py                ← Redis helpers (set_session, delete_session, get_user_id)
│   │   └── dao/
│   │       └── repository.py           ← LAYER 3: SQLAlchemy queries (get_by_email, create_user)
│   │
│   └── users/                          ← domain: profile read
│       ├── handler/
│       │   └── router.py               ← GET /users/me (requires session cookie)
│       ├── utils/
│       │   ├── service.py              ← fetch user from DB by id
│       │   └── schemas.py              ← UserResponse schema
│       └── dao/
│           └── repository.py           ← get_user_by_id query
│
├── migrations/
│   ├── env.py
│   └── versions/
│       └── 0001_create_users_table.py
│
└── tests/
    ├── conftest.py                      ← SQLite in-memory DB + AsyncMock Redis + ASGI client
    ├── test_auth.py                     ← register, login, logout endpoint tests
    └── test_users.py                    ← /users/me endpoint tests
```

**Layer rules (strictly enforced across all services):**

| Layer | File | Responsibility | Can call |
|-------|------|----------------|----------|
| 1 — Handler | `handler/router.py` | HTTP routing, request/response wiring | Service only |
| 2 — Service | `utils/service.py` | Business logic, orchestration | Repository + Cache |
| 3 — Repository | `dao/repository.py` | Raw SQLAlchemy queries | DB session only |
| Cache | `utils/cache.py` | Redis read/write helpers | Redis client only |

No layer skipping: **Router → Service → Repository / Cache**

---

## 📄 Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, component breakdown, data flows, LLD |
| [Database](docs/DATABASE.md) | PostgreSQL, Redis, Kafka schemas |
| [Heatmap Engine](docs/HEATMAP.md) | Heatmap engine design, bucket scoring, Redis key patterns |
| [Roadmap](docs/ROADMAP.md) | Build phases & implementation status |

### Service Technical References (`docs/service-working/`)

| File | Service |
|------|---------|
| [01-user-service.md](docs/service-working/01-user-service.md) | Auth, sessions, user profile |
| [02-video-service.md](docs/service-working/02-video-service.md) | Upload, metadata, Kafka events |
| [03-encoding-worker.md](docs/service-working/03-encoding-worker.md) | FFmpeg HLS transcode worker |
| [04-thumbnail-worker.md](docs/service-working/04-thumbnail-worker.md) | FFmpeg thumbnail worker |
| [05-streaming-service.md](docs/service-working/05-streaming-service.md) | HLS segment delivery |
| [06-summarization-service.md](docs/service-working/06-summarization-service.md) | Whisper + DistilBART AI pipeline |
| [07-trending-service.md](docs/service-working/07-trending-service.md) | Leaderboard + recommendations |
| [08-event-ingestion.md](docs/service-working/08-event-ingestion.md) | Interaction event write gateway |
| [09-heatmap-aggregator.md](docs/service-working/09-heatmap-aggregator.md) | Kafka → bucket scoring → Redis + MongoDB |
| [10-heatmap-api.md](docs/service-working/10-heatmap-api.md) | Heatmap read API (all-time / live / highlights) |

---

## 📊 Implementation Status

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | Infrastructure (Docker, Kafka, NGINX) | ✅ Done |
| 2 | User Service | ✅ Done |
| 3 | Video Service | ✅ Done |
| 4 | Encoding & Thumbnail Workers | ✅ Done |
| 5 | Streaming Service | ✅ Done |
| 6 | AI Summarization | ✅ Done |
| 7 | Trending & Recommendations | ✅ Done |
| 8a | Event Ingestion Service | ✅ Done |
| 8b | Heatmap Aggregator | ✅ Done |
| 8c | Heatmap API | ✅ Done |
| 9 | Frontend (React) | 🔲 Not started |
| 10 | Integration & Testing | 🔲 Not started |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy (async), Alembic |
| Workers | aiokafka, FFmpeg, OpenAI Whisper, DistilBART |
| Data | PostgreSQL 15, Redis 7, MongoDB 6, Apache Kafka |
| Gateway | NGINX |
| Infra | Docker Compose |
| Frontend (planned) | React 18, Vite, hls.js |

---

## 🧩 Running Services Individually

Use these commands when you want to start, rebuild, or debug a specific service without restarting the full stack.

### Step 1 — Start Infrastructure (required first)

```bash
# Start all infrastructure services
docker compose up -d postgres redis zookeeper kafka mongo nginx

# Wait for Kafka to be ready, then create topics
docker compose up kafka-setup
```

### Step 2 — Start Individual Services

```bash
# User Service (auth, sessions)
docker compose up -d user-service

# Video Service (upload, metadata)
docker compose up -d video-service

# Encoding Worker (FFmpeg HLS transcode) — needs Kafka topics
docker compose up -d encoding-worker

# Thumbnail Worker (FFmpeg thumbnail) — needs Kafka topics
docker compose up -d thumbnail-worker

# Streaming Service (HLS playback)
docker compose up -d streaming-service

# Summarization Service (Whisper + BART) — needs Kafka topics
docker compose up -d summarization-service

# Trending Service (leaderboard + recommendations) — needs Kafka + Redis
docker compose up -d trending-service

# Event Ingestion (interaction event gateway) — needs Kafka + Redis
docker compose up -d event-ingestion

# Heatmap Aggregator (Kafka consumer → Redis + MongoDB) — needs Kafka + Redis + MongoDB
docker compose up -d heatmap-aggregator

# Heatmap API (read endpoints) — needs Redis + MongoDB
docker compose up -d heatmap-api
```

### Rebuild a Single Service (after code changes)

```bash
docker compose up -d --build <service-name>

# Examples:
docker compose up -d --build user-service
docker compose up -d --build video-service
docker compose up -d --build encoding-worker
```

### View Logs for a Specific Service

```bash
docker compose logs -f user-service
docker compose logs -f video-service
docker compose logs -f encoding-worker
docker compose logs -f thumbnail-worker
docker compose logs -f streaming-service
docker compose logs -f summarization-service
docker compose logs -f trending-service
docker compose logs -f event-ingestion
docker compose logs -f heatmap-aggregator
docker compose logs -f heatmap-api
```

### Check Status

```bash
docker compose ps
```

### Stop a Single Service

```bash
docker compose stop <service-name>

# Restart without rebuild:
docker compose restart <service-name>
```

### Minimal Stack for API Testing (no workers/AI)

```bash
docker compose up -d postgres redis zookeeper kafka mongo nginx
docker compose up kafka-setup
docker compose up -d user-service video-service streaming-service
```

---

## 🔲 What's Left

### Phase 9 — Frontend (React 18 + Vite)
- Video player with HLS.js
- Auth pages (register / login)
- Upload flow with processing status polling
- Trending & recommendations feed
- AI summary panel alongside the player
- Heatmap overlay on video progress bar (fires `POST /events/interaction` on PLAY, PAUSE, SEEK, REWIND)

### Phase 10 — Integration & End-to-End Testing
- Full `docker compose up` smoke tests
- End-to-end flow: upload → encode → stream → summarize → trending → heatmap
- Final documentation pass

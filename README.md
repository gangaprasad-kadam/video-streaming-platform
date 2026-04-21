# Distributed Video Streaming Platform

A scalable distributed video streaming platform (YouTube/Netflix-style) built with microservices, event-driven architecture, and real-time analytics.

**Progress: 7 / 10 Phases Complete**

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
| shared/ | — | Common exceptions, response schemas, auth dependencies |

**Data Stores:** PostgreSQL (relational data), Redis (sessions & cache), MongoDB (worker error logs), Kafka (async event bus)

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
│   ├── user-service/                ← :8001
│   ├── video-service/               ← :8002
│   ├── encoding-worker/             ← Kafka consumer → FFmpeg HLS
│   ├── thumbnail-worker/            ← Kafka consumer → FFmpeg thumbnail
│   ├── streaming-service/           ← :8003
│   ├── summarization-service/       ← :8004
│   └── trending-service/            ← :8005
└── docs/
    ├── ARCHITECTURE.md              ← system design & LLD
    ├── DATABASE.md                  ← schemas (PostgreSQL, Redis, Kafka)
    ├── HEATMAP.md                   ← heatmap engine spec (planned)
    ├── ROADMAP.md                   ← all build phases & status
    ├── diagrams/                    ← architecture diagrams (PNG)
    ├── service-working/             ← per-service working guides
    └── test/                        ← per-service testing guides
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
| [Heatmap Engine](docs/HEATMAP.md) | Heatmap engine spec (planned — not yet implemented) |
| [Roadmap](docs/ROADMAP.md) | Build phases & implementation status |

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
| 8 | Heatmap Engine | 🔲 Not started |
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

### Phase 8 — Heatmap Engine
Three new services to build:

| Service | Port | Description |
|---------|------|-------------|
| `event-ingestion` | 8006 | `POST /events/interaction` → 202 + async Kafka publish; Redis rate limiting |
| `heatmap-aggregator` | — | Kafka consumer → per-second engagement scoring → MongoDB time-series |
| `heatmap-api` | 8007 | `GET /heatmap/{videoId}` → engagement curve data for player overlay |

### Phase 9 — Frontend (React 18 + Vite)
- Video player with HLS.js
- Auth pages (register / login)
- Upload flow with processing status polling
- Trending & recommendations feed
- AI summary panel alongside the player

### Phase 10 — Integration & End-to-End Testing
- Full `docker compose up` smoke tests
- End-to-end flow: upload → encode → stream → summarize → trending
- Final documentation pass

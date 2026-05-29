# VidStream — Distributed Video Streaming Platform

A full-stack, scalable distributed video streaming platform (YouTube/Netflix-style) built with **10 FastAPI microservices**, **Apache Kafka**, a **React 18 SPA**, and real-time analytics.

---

## ✅ Implementation Status

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | Infrastructure (Docker, Kafka, NGINX) | ✅ Complete |
| 2 | User Service (auth, sessions) | ✅ Complete |
| 3 | Video Service (upload, metadata) | ✅ Complete |
| 4 | Encoding & Thumbnail Workers | ✅ Complete |
| 5 | Streaming Service (HLS) | ✅ Complete |
| 6 | AI Summarization (Whisper + DistilBART) | ✅ Complete |
| 7 | Trending & Recommendations | ✅ Complete |
| 8a | Event Ingestion Service | ✅ Complete |
| 8b | Heatmap Aggregator | ✅ Complete |
| 8c | Heatmap API | ✅ Complete |
| 9 | Frontend (React 18 + Vite) | ✅ Complete |

---

## 🚀 Quick Start

The backend and frontend are started **independently**. Run them in two separate terminals.

---

### Prerequisites

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Docker | 24+ | `docker --version` |
| Docker Compose | v2 (plugin) | `docker compose version` |
| Node.js | 18+ | `node --version` |

---

### Terminal 1 — Start the Backend

```bash
cd project/backend

# First time only — copy and configure env
cp .env.example .env
# Edit .env and set: POSTGRES_PASSWORD, SESSION_SECRET

# Start all 10 microservices + databases + Kafka + NGINX
./start.sh
```

Backend API is now live at **http://localhost:80**

---

### Terminal 2 — Start the Frontend

**Option A — Development (recommended, hot-reload):**

```bash
cd project/frontend
npm install          # first time only
npm run dev          # starts at http://localhost:5173
```

Vite automatically proxies all API calls (`/auth`, `/videos`, etc.) to `http://localhost:80`.

**Option B — Docker (production build):**

```bash
cd project/frontend
docker compose up --build
```

Frontend is served at **http://localhost:3000** and proxies API calls to the backend.

---

### Stop

```bash
# Stop backend
cd project/backend && ./start.sh down

# Stop frontend (if running in Docker)
cd project/frontend && docker compose down
# Frontend dev server: Ctrl+C
```

---

## 🌐 Access Points

| What | URL | Notes |
|------|-----|-------|
| **Frontend (dev)** | http://localhost:5173 | `npm run dev` — hot reload |
| **Frontend (Docker)** | http://localhost:3000 | `docker compose up` in `frontend/` |
| Backend API Gateway | http://localhost:80 | NGINX — routes all `/auth`, `/videos`, etc. |
| User Service Swagger | http://localhost:8001/docs | — |
| Video Service Swagger | http://localhost:8002/docs | — |
| Streaming Swagger | http://localhost:8003/docs | — |
| Summarization Swagger | http://localhost:8004/docs | — |
| Trending Swagger | http://localhost:8005/docs | — |
| Event Ingestion Swagger | http://localhost:8006/docs | — |
| Heatmap API Swagger | http://localhost:8008/docs | — |

---

## 🛠️ Development Workflow

### Backend — rebuild a single service after code changes

```bash
cd backend
docker compose up -d --build <service-name>

# Examples:
docker compose up -d --build user-service
docker compose up -d --build video-service
docker compose up -d --build encoding-worker
```

### Frontend — hot-reload dev server

```bash
cd frontend
npm run dev          # http://localhost:5173  (proxies API to :80)
```

### Frontend — run tests

```bash
cd frontend
npm run test         # Vitest watch mode
npm run test:run     # single CI run (55 tests)
npm run test:coverage
```

### Frontend — rebuild Docker image after UI changes

```bash
cd frontend
docker compose up --build
```

### View backend logs

```bash
cd backend
./start.sh logs                          # tail ALL services
docker compose logs -f user-service      # single service
docker compose logs -f encoding-worker
```

### Check backend container health

```bash
cd backend
./start.sh status
# or
docker compose ps
```

---

## 🔬 Minimal Stack (API testing without workers/AI)

If you want to test the REST API without waiting for heavy workers:

```bash
cd backend
docker compose up -d postgres redis mongo zookeeper kafka nginx
docker compose up kafka-setup
docker compose up -d user-service video-service streaming-service
```

Access Swagger at http://localhost:8001/docs and http://localhost:8002/docs.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND  (independent)                            │
│                                                     │
│  Dev:    Vite dev server  :5173                     │
│  Docker: nginx container  :3000                     │
│                                                     │
│  React SPA makes API calls to backend on :80        │
└────────────────────┬────────────────────────────────┘
                     │  HTTP  (API calls)
                     ▼
┌─────────────────────────────────────────────────────┐
│  BACKEND  (independent)                             │
│                                                     │
│  NGINX API Gateway  :80                             │
│    ├─ /auth, /users   → user-service     :8001      │
│    ├─ /videos         → video-service    :8002      │
│    ├─ /stream         → streaming        :8003      │
│    ├─ /summary        → summarization    :8004      │
│    ├─ /trending       → trending         :8005      │
│    ├─ /events         → event-ingestion  :8006      │
│    └─ /heatmap        → heatmap-api      :8008      │
│                                                     │
│  Apache Kafka  ←→  encoding-worker                  │
│                ←→  thumbnail-worker                 │
│                ←→  summarization-service            │
│                ←→  trending-service                 │
│                ←→  heatmap-aggregator               │
│                                                     │
│  PostgreSQL  │  Redis  │  MongoDB                   │
└─────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
project/
├── backend/
│   ├── docker-compose.yml       ← backend microservices + infrastructure orchestration
│   ├── .env / .env.example      ← environment config
│   ├── start.sh                 ← one-command startup script
│   ├── nginx/
│   │   └── nginx.conf           ← API gateway + SPA proxy (port 80)
│   └── services/
│       ├── shared/              ← common Python module (exceptions, schemas, auth dep)
│       ├── user-service/        ← :8001  auth & user profiles
│       ├── video-service/       ← :8002  upload, metadata, Kafka events
│       ├── encoding-worker/     ← Kafka consumer → FFmpeg HLS transcode
│       ├── thumbnail-worker/    ← Kafka consumer → FFmpeg thumbnail
│       ├── streaming-service/   ← :8003  HLS segment delivery
│       ├── summarization-service/ ← :8004 Whisper + DistilBART
│       ├── trending-service/    ← :8005  leaderboard + recommendations
│       ├── event-ingestion/     ← :8006  interaction event → Kafka
│       ├── heatmap-aggregator/  ← :8007  Kafka → Redis + MongoDB bucket scoring
│       └── heatmap-api/         ← :8008  heatmap read API (all-time / live / highlights)
│
├── frontend/                    ← React 18 + Vite SPA  (started independently)
│   ├── docker-compose.yml       ← standalone frontend Docker stack (port 3000)
│   ├── Dockerfile               ← multi-stage: node:20 build → nginx:alpine serve
│   ├── nginx.conf.template      ← nginx config with ${BACKEND_URL} substitution
│   ├── vite.config.js           ← path aliases, dev proxy to :80, Vitest config
│   ├── .env.example
│   └── src/
│       ├── api/                 ← Axios client + per-service API modules
│       ├── context/             ← AuthContext (login, logout, register, session rehydrate)
│       ├── hooks/               ← useTheme, useVideoStatus, useInteractionTracker, useHeatmapSSE
│       ├── components/          ← Navbar, HlsPlayer, VideoCard, VideoGrid,
│       │                           SummaryPanel, HeatmapChart, UploadProgressBar
│       ├── pages/               ← Login, Register, Home, Browse, Player, Upload, Dashboard
│       └── styles/              ← global.css (design tokens, dark/light theme, utilities)
│
└── docs/
    ├── ARCHITECTURE.md
    ├── DATABASE.md
    ├── HEATMAP.md
    ├── ROADMAP.md
    ├── FRONTEND_PLAN.md         ← Phase 9 module plan + 74 test cases
    └── service-working/         ← per-service technical reference docs
```

---

## 🏛️ Backend Service Architecture

Every service follows a strict **three-layer architecture**:

| Layer | File | Responsibility |
|-------|------|----------------|
| 1 — Handler | `handler/router.py` | HTTP routing, request/response wiring |
| 2 — Service | `utils/service.py` | Business logic, orchestration |
| 3 — Repository | `dao/repository.py` | SQLAlchemy DB queries |
| Cache | `utils/cache.py` | Redis read/write helpers |

**No layer skipping: Router → Service → Repository / Cache**

---

## 🎨 Frontend Features

- **Dark / Light theme** toggle with `localStorage` persistence
- **VidStream teal** design system (`#00c9a7`) — CSS custom properties
- **HLS video player** via hls.js with Safari native fallback
- **Interaction tracking** — PLAY, PAUSE, SEEK, REWIND events sent to `/events/interaction`
- **AI Summary panel** — Whisper transcript + DistilBART key moments with seek-to
- **Live heatmap** — SSE-powered engagement chart updates in real time
- **Drag-and-drop upload** with encoding status polling
- **55 unit tests** (Vitest + Testing Library) — all passing

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy (async), Alembic, Pydantic v2 |
| AI/ML | OpenAI Whisper, DistilBART (Hugging Face) |
| Workers | aiokafka, FFmpeg |
| Data | PostgreSQL 15, Redis 7, MongoDB 6, Apache Kafka + Zookeeper |
| Gateway | NGINX (API routing + SPA proxy) |
| Frontend | React 18, Vite, React Router v6, Axios, hls.js, Recharts |
| Testing | Vitest, Testing Library, jsdom |
| Infra | Docker Compose (multi-stage builds) |

---

## 📄 Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, data flows, component breakdown |
| [Database](docs/DATABASE.md) | PostgreSQL, Redis, Kafka schemas |
| [Heatmap Engine](docs/HEATMAP.md) | Bucket scoring, Redis key patterns, SSE streaming |
| [Roadmap](docs/ROADMAP.md) | Build phases and completion status |
| [Frontend Plan](docs/FRONTEND_PLAN.md) | Phase 9 module plan + 74 test case specs |

### Service Reference Docs (`docs/service-working/`)

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

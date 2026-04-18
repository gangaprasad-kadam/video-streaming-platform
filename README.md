# Distributed Video Streaming Platform

A scalable distributed video streaming platform (YouTube/Netflix-style) built with microservices, event-driven architecture, and real-time analytics.

**Unique Feature 🔥** — Viewer Behavior Heatmap Engine: real-time per-second engagement analytics overlaid on the video player.

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

**Endpoints** (via NGINX on port 80):

| Route | Service | Docs |
|-------|---------|------|
| `/auth/*`, `/users/*` | user-service | http://localhost:8001/docs |
| `/videos/*` | video-service | http://localhost:8002/docs |

---

## 🏗️ Architecture

```
Browser → NGINX (port 80) → Microservices → Data Stores
                                ↕
                          Apache Kafka
```

- **user-service** (8001) — Registration, login, session auth (Redis)
- **video-service** (8002) — Video upload, metadata CRUD, Kafka events
- **shared/** — Common exceptions, schemas, auth dependencies

**Data Stores:** PostgreSQL (relational), Redis (sessions/cache), Kafka (async events)

---

## 📂 Project Structure

```
project/
├── docker-compose.yml
├── .env / .env.example
├── start.sh
├── nginx/nginx.conf
├── services/
│   ├── shared/            ← common Python utilities
│   ├── user-service/      ← :8001 (auth, users)
│   └── video-service/     ← :8002 (upload, metadata)
└── docs/
    ├── ARCHITECTURE.md    ← system design & LLD
    ├── DATABASE.md        ← schemas (PostgreSQL, Redis, Kafka)
    ├── HEATMAP.md         ← unique feature spec
    ├── ROADMAP.md         ← all build phases & status
    └── diagrams/          ← architecture diagrams (PNG)
```

---

## 📄 Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design, component breakdown, data flows, LLD |
| [Database](docs/DATABASE.md) | PostgreSQL, Redis, Kafka schemas |
| [Heatmap Engine](docs/HEATMAP.md) | Unique feature deep-dive |
| [Roadmap](docs/ROADMAP.md) | Build phases & implementation status |

---

## 📊 Implementation Status

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | Infrastructure (Docker, Kafka, NGINX) | ✅ Done |
| 2 | User Service | ✅ Done |
| 3 | Video Service | ✅ Done |
| 4 | Encoding & Thumbnail Workers | 🔲 Not started |
| 5 | Streaming Service | 🔲 Not started |
| 6 | AI Summarization | 🔲 Not started |
| 7 | Trending & Recommendations | 🔲 Not started |
| 8 | Heatmap Engine | 🔲 Not started |
| 9 | Frontend (React) | 🔲 Not started |
| 10 | Integration & Testing | 🔲 Not started |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy (async), Alembic |
| Data | PostgreSQL 15, Redis 7, Apache Kafka |
| Gateway | NGINX |
| Infra | Docker Compose |
| Frontend (planned) | React 18, Vite, hls.js |
# 📋 Project Phases — Index

## Project: Distributed Video Streaming Platform

**Stack:** Python (FastAPI) · React.js · Docker Compose · Kafka · Redis · PostgreSQL · MongoDB  
**Auth:** Session-based (Redis)  
**AI:** Whisper + HuggingFace Transformers  
**Unique Feature:** 🔥 Viewer Behavior Heatmap Engine  

---

## Phase Overview

| # | Phase | Services Created | Key Concepts |
|---|---|---|---|
| [DB](../database-design.md) | **Database Design** | — | PostgreSQL schemas, Redis keys, MongoDB, Kafka events |
| [Shared](./shared-patterns.md) | **Shared Patterns** | `services/shared/` | Layered arch, exceptions, response envelope, config template |
| [1](./phase-1-infrastructure.md) | Infrastructure & Skeleton | — | Docker, Kafka, Redis, PostgreSQL, NGINX |
| [2](./phase-2-user-service.md) | User Service | `user-service` | Session auth, bcrypt, PostgreSQL |
| [3](./phase-3-video-service.md) | Video Service | `video-service` | File upload, Kafka producer, PostgreSQL |
| [4](./phase-4-processing-pipeline.md) | Processing Pipeline | `encoding-worker`, `thumbnail-worker` | Kafka consumers, ffmpeg, async processing |
| [5](./phase-5-streaming-service.md) | Streaming Service | `streaming-service` | HLS, Redis cache, sync reads |
| [6](./phase-6-ai-summarization.md) | AI Summarization | `summarization-service` | Whisper, BART, Kafka consumer |
| [7](./phase-7-trending-recommendations.md) | Trending & Recommendations | `trending-service` | Redis sorted sets, Kafka consumer |
| [8](./phase-8-heatmap-engine.md) | Heatmap Engine ⭐ | `event-ingestion`, `heatmap-aggregator`, `heatmap-api` | Async ingest, Kafka, Redis counters, SSE |
| [9](./phase-9-frontend.md) | Frontend | `frontend` | React, hls.js, creator dashboard |
| [10](./phase-10-integration.md) | Integration & Docs | — | E2E testing, final docs |

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

---

## Folder Structure (Final)

```
project/
├── docker-compose.yml
├── .env.example
├── nginx/
│   └── nginx.conf
├── services/
│   ├── user-service/
│   ├── video-service/
│   ├── encoding-worker/
│   ├── thumbnail-worker/
│   ├── streaming-service/
│   ├── summarization-service/
│   ├── trending-service/
│   ├── event-ingestion/
│   ├── heatmap-aggregator/
│   └── heatmap-api/
├── frontend/
└── docs/
    ├── intro.md
    ├── unique-feature.md
    └── phases/
        ├── README.md  ← you are here
        ├── phase-1-infrastructure.md
        ├── phase-2-user-service.md
        ├── phase-3-video-service.md
        ├── phase-4-processing-pipeline.md
        ├── phase-5-streaming-service.md
        ├── phase-6-ai-summarization.md
        ├── phase-7-trending-recommendations.md
        ├── phase-8-heatmap-engine.md
        ├── phase-9-frontend.md
        └── phase-10-integration.md
```

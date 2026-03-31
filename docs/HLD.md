# 🏗️ High-Level Design (HLD)

## Distributed Video Streaming Platform

---

## 📐 System Architecture Diagram

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
   │  ║                                                 ║   │
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
   │
   ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                           DATA STORES                                   ║
║                                                                         ║
║  ┌──────────────────┐   ┌────────────────────┐   ┌──────────────────┐  ║
║  │  PostgreSQL :5432│   │   Redis :6379       │   │ MongoDB :27017   │  ║
║  │                  │   │                     │   │                  │  ║
║  │ • users          │   │ • session:{sid}     │   │ • processing_logs│  ║
║  │ • videos         │   │ • trending:videos   │   │ • error_logs     │  ║
║  │ • video_summaries│   │ • heatmap:{vid}:*   │   │                  │  ║
║  │ • watch_history  │   │ • summary:{vid}     │   │ (TTL auto-rotate)│  ║
║  │ • viewer_events  │   │ • stream:manifest:* │   └──────────────────┘  ║
║  │ • heatmap_snap.. │   │ • ratelimit:events:*│                         ║
║  │ • viral_alerts   │   └────────────────────┘                         ║
║  └──────────────────┘                                                   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 🧱 Component Breakdown

### 1. 🖥️ Frontend — React 18 + Vite (port 3000)
The UI layer. Users browse, upload, and watch videos here.
- **hls.js** handles adaptive bitrate video playback
- **recharts** renders the live viewer heatmap overlay
- Communicates only with NGINX — never directly with microservices

---

### 2. 🚦 NGINX API Gateway (port 80)
The single entry point for all traffic.
- Routes `/api/users/*` → user-service
- Routes `/api/videos/*` → video-service
- Routes `/stream/*` → streaming-service
- Routes `/api/events/*` → event-ingestion
- Serves React frontend as static files
- Enforces global rate limiting

---

### 3. 🔧 Microservices

| Service | Port | Responsibility |
|---|---|---|
| **user-service** | 8001 | Register · login · session auth (Redis) |
| **video-service** | 8002 | Upload metadata · trigger Kafka `video.uploaded` |
| **streaming-service** | 8003 | Serve HLS manifests + `.ts` chunks from disk |
| **summarization-service** | 8004 | Whisper transcription → BART summary → cache |
| **trending-service** | 8005 | ZINCRBY in Redis → leaderboard via ZREVRANGE |
| **event-ingestion** | 8006 | Accept viewer events (202 Accepted) → Kafka |
| **heatmap-api** | 8007 | Serve heatmap data · SSE live feed · highlights |

---

### 4. ⚙️ Background Workers (Kafka Consumers, no HTTP port)

| Worker | Consumes | Produces | Does |
|---|---|---|---|
| **encoding-worker** | `video.uploaded` | `video.processed` | ffmpeg → 360p/720p/1080p HLS |
| **thumbnail-worker** | `video.uploaded` | — | ffmpeg → thumbnail image |
| **heatmap-aggregator** | `viewer-interaction-events` | `heatmap-aggregated`, `heatmap-alerts` | 5-second bucket INCR in Redis · flush to PostgreSQL · spike detection |

---

### 5. 📨 Kafka Event Bus
All async communication flows through Kafka. Services are **never** directly coupled.

```
User watches video
   └─▶ event-ingestion (202 immediately, never blocks playback)
         └─▶ Kafka: viewer-interaction-events
               ├─▶ heatmap-aggregator (increments Redis counters)
               └─▶ trending-service (updates leaderboard)

Creator uploads video
   └─▶ video-service (stores metadata)
         └─▶ Kafka: video.uploaded
               ├─▶ encoding-worker (produces HLS files)
               │     └─▶ Kafka: video.processed
               │           └─▶ summarization-service (Whisper + BART)
               └─▶ thumbnail-worker (extracts thumbnail)
```

---

### 6. 🗄️ Data Stores

| Store | Purpose | Why |
|---|---|---|
| **PostgreSQL** | Users, videos, heatmaps, history | Relational, ACID transactions |
| **Redis** | Sessions, heatmap counters, trending sorted set, manifest cache | Sub-millisecond reads; TTL support |
| **MongoDB** | Processing logs, error logs | Flexible schema; TTL auto-rotation |

---

## 🔥 Unique Feature: Viewer Behavior Heatmap Engine

The standout feature. Every 5-second segment of every video has a real-time "heat" score showing how many viewers watched that exact moment.

```
Viewer plays second 47 of a video
   └─▶ Frontend fires POST /api/events  { type: PLAY, position: 47 }
         └─▶ event-ingestion returns 202 immediately
               └─▶ Kafka: viewer-interaction-events
                     └─▶ heatmap-aggregator:
                           • bucket = floor(47 / 5) = segment 9
                           • INCR heatmap:{vid}:live:9
                           • INCR heatmap:{vid}:total:9
                           • If spike > 3× baseline → publish heatmap-alerts
                           • Every hour: flush Redis → PostgreSQL snapshot
```

The heatmap renders as a color gradient bar beneath the video player — red = most-watched, blue = least-watched.

---

## 🔄 End-to-End Flows

### Upload Flow
```
Creator → NGINX → video-service → PostgreSQL (metadata)
                               → Kafka: video.uploaded
                                     → encoding-worker → HLS files on disk
                                     │                 → Kafka: video.processed
                                     │                       → summarization-service
                                     │                             → Whisper (audio→text)
                                     │                             → BART (text→summary)
                                     │                             → PostgreSQL + Redis
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

## 🏛️ Key Design Decisions

| Decision | Reason |
|---|---|
| **Session auth (not JWT)** | Simpler revocation; Redis already in stack |
| **No service-to-service REST calls** | Tight coupling avoided; Kafka + shared Redis instead |
| **202 for viewer events** | Viewer events must NEVER block video playback |
| **HLS (not DASH)** | Better browser support with hls.js |
| **5-second heatmap buckets** | Fine-grained insight without storage explosion |
| **Redis sorted set for trending** | `ZINCRBY` + `ZREVRANGE` = O(log N) leaderboard |
| **Whisper `base` model** | Runs on CPU; acceptable accuracy for a college project |
| **Docker Compose** | Single `docker-compose up` brings up all 16 containers |

---

## 🗂️ Final Folder Structure

```
project/
├── docker-compose.yml          ← all 16 containers
├── .env.example                ← environment variable template
├── nginx/
│   └── nginx.conf
├── services/
│   ├── shared/                 ← Python package shared by all services
│   ├── user-service/           ← :8001
│   ├── video-service/          ← :8002
│   ├── encoding-worker/        ← Kafka consumer
│   ├── thumbnail-worker/       ← Kafka consumer
│   ├── streaming-service/      ← :8003
│   ├── summarization-service/  ← :8004
│   ├── trending-service/       ← :8005
│   ├── event-ingestion/        ← :8006
│   ├── heatmap-aggregator/     ← Kafka consumer
│   └── heatmap-api/            ← :8007
├── frontend/                   ← React + Vite
└── docs/
    ├── HLD.md                  ← this file
    ├── COPILOT.md              ← AI session reference
    ├── database-design.md      ← full schema
    ├── lld.md                  ← low-level design per service
    ├── unique-feature.md       ← heatmap engine deep-dive
    └── phases/                 ← per-phase implementation guides
```

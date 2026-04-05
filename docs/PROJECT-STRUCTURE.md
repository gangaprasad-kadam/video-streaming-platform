# 📁 Final Project Structure

> **This is the finalized folder structure for the entire platform.**
> Every service follows a consistent Django-inspired **3-Layer Architecture**.
> Read this before implementing any service.

---

## 🏛️ The 3-Layer Pattern (Applied to Every Service)

Inspired by Django's separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — PRESENTATION                                     │
│  router.py  ·  schemas.py                                   │
│  (Django equivalent: urls.py + views.py + serializers.py)   │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2 — BUSINESS LOGIC                                   │
│  service.py                                                 │
│  (Django equivalent: services.py / model methods)           │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3 — DATA                                             │
│  model.py  ·  repository.py  ·  cache.py  ·  migrations/   │
│  (Django equivalent: models.py + migrations/ + managers)    │
└─────────────────────────────────────────────────────────────┘
```

**Rule:** Data only flows downward.
- Router calls Service. Service calls Repository/Cache. Never the reverse.
- Router never touches DB directly. Repository never has business logic.

---

## 📂 Complete Project Tree

```
project/
│
├── docker-compose.yml              ← Starts all 16 containers with one command
├── .env                            ← Secrets (gitignored)
├── .env.example                    ← Committed template
│
├── nginx/
│   └── nginx.conf                  ← Routes + rate limiting + static serving
│
├── services/
│   │
│   ├── shared/                     ← Python package mounted into EVERY service (read-only)
│   │   ├── __init__.py
│   │   ├── dependencies.py         ← get_db(), get_redis(), get_current_user()
│   │   ├── exceptions.py           ← AppException base + standard HTTP error codes
│   │   └── schemas.py              ← SuccessResponse[T], ErrorResponse, PagedResponse[T]
│   │
│   ├── user-service/               ← Port 8001
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── app/
│   │       ├── main.py             ← FastAPI app + lifespan hooks + 3 exception handlers
│   │       ├── config.py           ← Pydantic BaseSettings (reads .env)
│   │       ├── database.py         ← SQLAlchemy async engine + session factory
│   │       ├── redis_client.py     ← Async Redis connection singleton
│   │       ├── models.py           ← [L3] ALL SQLAlchemy ORM models for this service
│   │       ├── exceptions.py       ← EmailConflict, AuthError, UserNotFound
│   │       │
│   │       ├── auth/               ← Domain: Authentication
│   │       │   ├── __init__.py
│   │       │   ├── router.py       ← [L1] POST /register, POST /login, POST /logout
│   │       │   ├── schemas.py      ← [L1] RegisterRequest, LoginRequest, UserResponse
│   │       │   ├── service.py      ← [L2] register(), login(), logout()
│   │       │   ├── repository.py   ← [L3] get_by_email(), create_user()
│   │       │   └── cache.py        ← [L3] set_session(), get_session(), delete_session()
│   │       │
│   │       └── users/              ← Domain: User Profile
│   │           ├── __init__.py
│   │           ├── router.py       ← [L1] GET /me
│   │           ├── schemas.py      ← [L1] UserProfileResponse
│   │           ├── service.py      ← [L2] get_me()
│   │           └── repository.py   ← [L3] get_user_by_id()
│   │
│   ├── video-service/              ← Port 8002
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── redis_client.py
│   │       ├── kafka_producer.py   ← Publishes to: video.uploaded
│   │       ├── models.py           ← [L3] Video SQLAlchemy model
│   │       ├── exceptions.py       ← VideoNotFound, ForbiddenAccess
│   │       │
│   │       └── videos/             ← Domain: Video Management
│   │           ├── __init__.py
│   │           ├── router.py       ← [L1] POST /upload, GET /{id}, GET /list, DELETE /{id}
│   │           ├── schemas.py      ← [L1] VideoUploadRequest, VideoResponse, VideoListResponse
│   │           ├── service.py      ← [L2] upload(), get_video(), list_videos(), delete_video()
│   │           ├── repository.py   ← [L3] create(), get_by_id(), list_by_creator(), update_status()
│   │           └── cache.py        ← [L3] cache video metadata for fast reads
│   │
│   ├── encoding-worker/            ← No HTTP port (Kafka consumer only)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── app/
│   │       ├── main.py             ← Kafka consumer runner loop (no FastAPI)
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── kafka_consumer.py   ← Consumes: video.uploaded
│   │       ├── kafka_producer.py   ← Publishes: video.processed
│   │       ├── models.py           ← [L3] Video model (status updates only)
│   │       │
│   │       └── encoding/           ← Domain: Video Encoding
│   │           ├── __init__.py
│   │           ├── service.py      ← [L2] encode_video() — ffmpeg 360p/720p/1080p HLS
│   │           └── repository.py   ← [L3] update_status(), update_hls_path()
│   │
│   ├── thumbnail-worker/           ← No HTTP port (Kafka consumer only)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← Kafka consumer runner
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── kafka_consumer.py   ← Consumes: video.uploaded
│   │       ├── models.py           ← [L3] Video model (thumbnail_path update)
│   │       │
│   │       └── thumbnail/          ← Domain: Thumbnail Extraction
│   │           ├── __init__.py
│   │           ├── service.py      ← [L2] extract_thumbnail() — ffmpeg frame at 5s
│   │           └── repository.py   ← [L3] update_thumbnail_path()
│   │
│   ├── streaming-service/          ← Port 8003
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── redis_client.py
│   │       │
│   │       └── streaming/          ← Domain: HLS Video Delivery
│   │           ├── __init__.py
│   │           ├── router.py       ← [L1] GET /{videoId}/manifest.m3u8
│   │           │                        GET /{videoId}/{segment}.ts
│   │           ├── schemas.py      ← [L1] ManifestResponse, SegmentHeaders
│   │           ├── service.py      ← [L2] get_manifest(), get_segment(), validate_ready()
│   │           └── cache.py        ← [L3] get_cached_manifest(), cache_manifest()
│   │
│   ├── summarization-service/      ← Port 8004
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── redis_client.py
│   │       ├── kafka_consumer.py   ← Consumes: video.processed
│   │       ├── models.py           ← [L3] VideoSummary SQLAlchemy model
│   │       ├── exceptions.py       ← SummaryNotFound, ModelNotReady
│   │       │
│   │       └── summarization/      ← Domain: AI Summarization
│   │           ├── __init__.py
│   │           ├── router.py       ← [L1] GET /{videoId}/summary
│   │           ├── schemas.py      ← [L1] SummaryResponse (transcript + summary)
│   │           ├── service.py      ← [L2] transcribe() → Whisper
│   │           │                        summarize() → BART
│   │           │                        get_summary() → cache-aside
│   │           ├── repository.py   ← [L3] create_summary(), get_by_video_id()
│   │           └── cache.py        ← [L3] cache_summary(), get_cached_summary()
│   │
│   ├── trending-service/           ← Port 8005
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── redis_client.py
│   │       ├── kafka_consumer.py   ← Consumes: viewer-interaction-events
│   │       ├── models.py           ← [L3] WatchHistory SQLAlchemy model
│   │       │
│   │       └── trending/           ← Domain: Trending + Recommendations
│   │           ├── __init__.py
│   │           ├── router.py       ← [L1] GET /trending
│   │           │                        GET /recommendations/{userId}
│   │           ├── schemas.py      ← [L1] TrendingResponse, RecommendationResponse
│   │           ├── service.py      ← [L2] get_trending(), update_score()
│   │           │                        get_recommendations(), apply_decay()
│   │           ├── repository.py   ← [L3] upsert_watch_history(), get_user_history()
│   │           └── cache.py        ← [L3] zincrby_score(), zrevrange_top10()
│   │
│   ├── event-ingestion/            ← Port 8006
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── redis_client.py
│   │       ├── kafka_producer.py   ← Publishes: viewer-interaction-events
│   │       │
│   │       └── events/             ← Domain: Viewer Event Collection
│   │           ├── __init__.py
│   │           ├── router.py       ← [L1] POST /events → returns 202 IMMEDIATELY
│   │           ├── schemas.py      ← [L1] ViewerEventRequest (type, videoId, position, timestamp)
│   │           ├── service.py      ← [L2] ingest_event() — rate check → Kafka publish
│   │           └── cache.py        ← [L3] check_rate_limit(), increment_counter()
│   │
│   ├── heatmap-aggregator/         ← No HTTP port (Kafka consumer only)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   └── app/
│   │       ├── main.py             ← Kafka consumer + hourly flush scheduler
│   │       ├── config.py
│   │       ├── database.py
│   │       ├── redis_client.py
│   │       ├── kafka_consumer.py   ← Consumes: viewer-interaction-events
│   │       ├── kafka_producer.py   ← Publishes: heatmap-aggregated, heatmap-alerts
│   │       ├── models.py           ← [L3] ViewerEvent, HeatmapSnapshot, ViralAlert models
│   │       │
│   │       └── heatmap/            ← Domain: Heatmap Aggregation
│   │           ├── __init__.py
│   │           ├── service.py      ← [L2] aggregate_event() — bucket = pos ÷ 5
│   │           │                        check_spike() — live > 3× baseline?
│   │           │                        flush_to_db() — hourly Redis → PostgreSQL
│   │           ├── repository.py   ← [L3] save_snapshot(), save_alert(), bulk_insert_events()
│   │           └── cache.py        ← [L3] incr_live(), incr_total(), get_baseline()
│   │                                       get_all_segments(), flush_live_counters()
│   │
│   └── heatmap-api/                ← Port 8007
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── main.py
│           ├── config.py
│           ├── redis_client.py
│           ├── kafka_consumer.py   ← Consumes: heatmap-aggregated (for SSE live feed)
│           │
│           └── heatmap/            ← Domain: Heatmap Data Serving
│               ├── __init__.py
│               ├── router.py       ← [L1] GET /{videoId}/heatmap   — full heatmap
│               │                        GET /{videoId}/highlights  — top 5 segments
│               │                        GET /{videoId}/live (SSE)  — real-time stream
│               ├── schemas.py      ← [L1] HeatmapResponse, SegmentScore, HighlightResponse
│               ├── service.py      ← [L2] get_heatmap(), get_highlights(), stream_live()
│               └── cache.py        ← [L3] get_all_segment_scores(), get_live_score()
│                                           get_heatmap_summary()
│
├── frontend/                       ← React 18 + Vite — Port 3000
│   ├── package.json
│   ├── vite.config.js
│   ├── .env.local                  ← VITE_API_BASE_URL=http://localhost
│   ├── index.html
│   └── src/
│       ├── main.jsx                ← React entry point
│       ├── App.jsx                 ← Router setup (React Router)
│       │
│       ├── pages/                  ← [L1] Full page components (like Django templates)
│       │   ├── HomePage.jsx        ← trending feed + search
│       │   ├── WatchPage.jsx       ← video player + heatmap + summary
│       │   ├── UploadPage.jsx      ← upload form + progress
│       │   ├── LoginPage.jsx       ← login form
│       │   └── RegisterPage.jsx    ← registration form
│       │
│       ├── components/             ← [L1] Reusable UI building blocks
│       │   ├── VideoPlayer.jsx     ← hls.js adaptive bitrate player
│       │   ├── HeatmapBar.jsx      ← recharts color gradient (🔴→🔵)
│       │   ├── VideoCard.jsx       ← thumbnail + title + views card
│       │   ├── TrendingList.jsx    ← ranked video list
│       │   ├── SummaryPanel.jsx    ← AI summary display
│       │   └── Navbar.jsx          ← top navigation
│       │
│       ├── hooks/                  ← [L2] Business Logic — custom React hooks
│       │   ├── useAuth.js          ← login state, session check
│       │   ├── useVideo.js         ← video fetch, upload progress
│       │   ├── useHeatmap.js       ← heatmap fetch + SSE live updates
│       │   └── useTrending.js      ← trending feed polling
│       │
│       ├── store/                  ← [L2] Global State Management
│       │   ├── authStore.js        ← current user, login/logout actions
│       │   └── videoStore.js       ← current playing video state
│       │
│       ├── services/               ← [L3] Data Layer — all API calls live here
│       │   ├── api.js              ← axios instance (baseURL + cookie credentials)
│       │   ├── authApi.js          ← register(), login(), logout(), getMe()
│       │   ├── videoApi.js         ← uploadVideo(), getVideo(), listVideos(), deleteVideo()
│       │   ├── streamingApi.js     ← getManifestUrl(), getSegmentUrl()
│       │   ├── heatmapApi.js       ← getHeatmap(), getHighlights(), subscribeToLive()
│       │   ├── trendingApi.js      ← getTrending(), getRecommendations()
│       │   └── summaryApi.js       ← getSummary()
│       │
│       └── utils/                  ← Pure helper functions (no side effects)
│           ├── formatters.js       ← formatDuration(), formatViews(), formatDate()
│           └── constants.js        ← EVENT_TYPES, VIDEO_STATUS, API_ROUTES
│
└── docs/
    ├── COPILOT.md                  ← AI session reference + build status
    ├── HLD.md                      ← Architecture overview
    ├── lld.md                      ← Low-level design per service
    ├── database-design.md          ← Full schema + ER diagram
    ├── unique-feature.md           ← Heatmap engine deep-dive
    ├── PROJECT-OVERVIEW.md         ← Non-technical full overview
    ├── PROJECT-STRUCTURE.md        ← This file
    └── diagrams/
        ├── 01-high-level-overview.png
        ├── 02-upload-flow.png
        ├── 03-watch-flow.png
        ├── 04-key-flows.png
        └── 05-kafka-topics.png
```

---

## 🗂️ Layer Reference Per File

| File | Layer | Django Equivalent | Responsibility |
|---|---|---|---|
| `{domain}/router.py` | L1 — Presentation | `urls.py` + `views.py` | HTTP routes, auth deps, call service |
| `{domain}/schemas.py` | L1 — Presentation | `serializers.py` | Pydantic request/response models |
| `{domain}/service.py` | L2 — Business Logic | `services.py` | All business rules, no raw SQL |
| `models.py` | L3 — Data | `models.py` | ALL SQLAlchemy ORM models for this service |
| `{domain}/repository.py` | L3 — Data | QuerySet managers | Only DB queries, returns domain objects |
| `{domain}/cache.py` | L3 — Data | — | Only Redis get/set/expire/incr |
| `migrations/` | L3 — Data | `migrations/` | Alembic schema versions (at service root) |
| `config.py` | Infrastructure | `settings.py` | Environment variables via Pydantic |
| `database.py` | Infrastructure | `db.py` | SQLAlchemy engine + session |
| `kafka_producer.py` / `kafka_consumer.py` | Infrastructure | — | Kafka producer/consumer setup |
| `exceptions.py` | Cross-cutting | exceptions | Service-wide custom exception classes |

---

## ⚙️ Service Internal Data Flow

```
HTTP Request
     │
     ▼
 router.py          ← validates input (Pydantic schemas)
     │                 injects auth dep (get_current_user)
     ▼                 calls service with clean data
 service.py         ← all business logic lives here
     │                 raises domain exceptions
     ├──────────────►  repository.py  ← SQLAlchemy queries only
     ├──────────────►  cache.py       ← Redis ops only
     └──────────────►  kafka_producer ← fire-and-forget events
          │
          ▼
     PostgreSQL / Redis / Kafka
```

---

## 🔀 Kafka Worker Data Flow

```
Kafka Message
     │
     ▼
 kafka_consumer.py  ← receives message, deserializes payload
     │
     ▼
 service.py         ← business logic (idempotency check first)
     │
     ├──────────────►  repository.py  ← DB updates
     ├──────────────►  cache.py       ← Redis updates
     └──────────────►  kafka_producer ← publish to next topic (if any)
```

---

## 📜 Naming Conventions

| Element | Convention | Example |
|---|---|---|
| File names | `snake_case.py` | `auth_service.py` |
| Class names | `PascalCase` | `AuthService`, `UserRepository` |
| Function names | `snake_case` | `get_by_email()`, `create_user()` |
| Router prefix | `/api/{domain}` | `/api/users`, `/api/videos` |
| SQLAlchemy model | Singular noun | `User`, `Video`, `HeatmapSnapshot` |
| Pydantic schema | `{Action}{Resource}{Request|Response}` | `VideoUploadRequest`, `UserResponse` |
| Kafka topics | `{domain}.{event}` or `{domain}-{event}` | `video.uploaded`, `heatmap-alerts` |
| Redis keys | `{namespace}:{id}:{field}` | `heatmap:abc123:live:9` |

---

## 🚫 Rules That Cannot Be Broken

1. **Router never imports from `repository.py`** — must go through `service.py`
2. **Service never uses SQLAlchemy directly** — always through `repository.py`
3. **Repository never has `if` business logic** — only query construction
4. **Cache never falls through to DB** — returns `None` on miss; service decides what to do
5. **Every Kafka consumer checks idempotency first** — skip if already processed
6. **Every CPU-heavy call uses `run_in_executor`** — ffmpeg, Whisper, BART are blocking
7. **All responses use the standard envelope** — `{ data, message }` or `{ error, message, detail }`

---

> 📄 Generated as part of the Distributed Video Streaming Platform project
> 🏗️ Follow this structure exactly for every service implementation

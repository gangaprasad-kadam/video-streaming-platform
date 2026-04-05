# 🎬 Distributed Video Streaming Platform — Complete Project Overview

> **For everyone** — whether you are a developer, client, or non-technical stakeholder.
> This document explains what the platform is, how it works, and how every part connects.

---

## 📌 What Is This Project?

Think of it as a **mini YouTube / Netflix** — but built with **advanced engineering practices** used by real companies like Google and Netflix.

Users can:
- ✅ **Register & log in** securely
- ✅ **Upload videos** that get automatically processed
- ✅ **Watch videos** in high quality with adaptive bitrate (auto-adjusts to your internet speed)
- ✅ **Get AI-generated summaries** of videos automatically
- ✅ **See trending videos** in real-time
- ✅ **View a heatmap** showing which parts of a video are most watched

The **standout feature** is the 🔥 **Viewer Behavior Heatmap Engine** — a live color bar beneath every video showing how many people watched each exact second.

---

## 🧱 The Building Blocks (Services)

The platform is split into **independent services** — like departments in a company. Each does one job very well and communicates with others through a shared messaging system.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          THE PLATFORM AT A GLANCE                           │
│                                                                             │
│  👤 USER  →  🌐 BROWSER  →  🚦 GATEWAY  →  📦 SERVICES  →  🗄️ DATA STORES  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Full Architecture Diagram

```
╔════════════════════════════════════════════════════════════════════════════╗
║                        👤 USER'S BROWSER / DEVICE                          ║
║                                                                            ║
║   React Web App (what you see and click)                                   ║
║   • Video player (adapts to your internet speed automatically)             ║
║   • Heatmap bar (live color gradient showing most-watched moments)         ║
║   • Dashboard (trending, recommendations, upload form)                     ║
╚══════════════════════════════════╦═════════════════════════════════════════╝
                                   ║
                         All requests go here
                                   ║
                                   ▼
╔════════════════════════════════════════════════════════════════════════════╗
║                     🚦 NGINX — THE FRONT DOOR (Port 80)                    ║
║                                                                            ║
║  The single entry point. Like a hotel receptionist — routes every          ║
║  request to the right department. Also applies rate limits.                ║
║                                                                            ║
║  /api/users/*    →  User Service                                           ║
║  /api/videos/*   →  Video Service                                          ║
║  /stream/*       →  Streaming Service                                      ║
║  /api/events/*   →  Event Ingestion                                        ║
║  /api/trending/* →  Trending Service                                       ║
║  /api/heatmap/*  →  Heatmap API                                            ║
║  /               →  React App (static files)                               ║
╚═╦══════╦══════╦══════╦══════╦══════╦══════╦═══════════════════════════════╝
  ║      ║      ║      ║      ║      ║      ║
  ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
│👤  │ │🎬  │ │▶️  │ │🤖  │ │🔥  │ │📡  │ │📊  │
│User│ │Video│ │Strm│ │Summ│ │Trnd│ │Evnt│ │Heat│
│Svc │ │Svc  │ │Svc │ │Svc │ │Svc │ │Ing │ │API │
│8001│ │8002 │ │8003│ │8004│ │8005│ │8006│ │8007│
└─┬──┘ └──┬──┘ └─┬──┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘
  │       │      │       │      │      │      │
  │       │      │       │      │      │      │
  │       └──────┼───────┼──────┼──────┼──────┘
  │              │       │      │      │
  │    ╔══════════════════════════════════════════╗
  │    ║         📨 APACHE KAFKA EVENT BUS         ║
  │    ║    (The internal messaging system)        ║
  │    ║                                          ║
  │    ║  Like a postal service between services. ║
  │    ║  Producers drop messages. Consumers pick ║
  │    ║  them up when ready. Nothing is lost.    ║
  │    ║                                          ║
  │    ║  Topics (channels):                      ║
  │    ║  📼 video.uploaded        (3 lanes)      ║
  │    ║  ✅ video.processed       (3 lanes)      ║
  │    ║  👁️  viewer-events        (12 lanes)     ║
  │    ║  🌡️  heatmap-aggregated   (6 lanes)      ║
  │    ║  🚨 heatmap-alerts        (3 lanes)      ║
  │    ╚══════╦═══════════╦══════════╦════════════╝
  │           ║           ║          ║
  │           ▼           ▼          ▼
  │     ┌──────────┐ ┌──────────┐ ┌──────────────┐
  │     │⚙️ Encode │ │🖼️ Thumb  │ │🌡️ Heatmap   │
  │     │ Worker   │ │ Worker   │ │  Aggregator  │
  │     │(no port) │ │(no port) │ │  (no port)   │
  │     └────┬─────┘ └──────────┘ └──────┬───────┘
  │          │  video.processed           │
  │          ▼                     heatmap-aggregated
  │     ┌──────────────┐                  │
  │     │🤖 Summ. Svc  │◄─────────────────┘
  │     │   :8004      │
  │     └──────────────┘
  │
  ▼
╔════════════════════════════════════════════════════════════════════════════╗
║                           🗄️ DATA STORES                                   ║
║                                                                            ║
║  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐  ║
║  │   🐘 PostgreSQL      │  │   ⚡ Redis           │  │  🍃 MongoDB      │  ║
║  │   (Main Database)   │  │   (Cache & Speed)   │  │  (Logs Only)     │  ║
║  │                     │  │                     │  │                  │  ║
║  │ • users             │  │ • sessions          │  │ • process logs   │  ║
║  │ • videos            │  │ • trending board    │  │ • error logs     │  ║
║  │ • video summaries   │  │ • heatmap counters  │  │ (auto-deleted    │  ║
║  │ • watch history     │  │ • video summaries   │  │  after TTL)      │  ║
║  │ • viewer events     │  │ • stream manifests  │  └──────────────────┘  ║
║  │ • heatmap snapshots │  │ • rate limit tracks │                        ║
║  │ • viral alerts      │  └─────────────────────┘                        ║
║  └─────────────────────┘                                                  ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

## 🔄 How Key Flows Work (Step by Step)

### 1️⃣ Signing Up & Logging In

```
You type email + password → click Login
         │
         ▼
     🌐 Browser
         │  POST /api/users/login
         ▼
     🚦 NGINX
         │
         ▼
     👤 User Service (Port 8001)
         │
         ├─ Check password with bcrypt (secure hashing)
         │
         ├─ Create a SESSION ID (random unique token)
         │
         ├─ Store in ⚡ Redis:
         │    session:{your-session-id} = your-user-id
         │    (expires in 24 hours automatically)
         │
         └─ Send back:
              🍪 HttpOnly Cookie "session_id" (secure, browser stores it)
              ✅ "Login successful"

Every future request:
  Browser sends cookie automatically →
    User Service checks Redis →
      Found? ✅ You're authenticated
      Not found or expired? ❌ 401 Unauthorized
```

---

### 2️⃣ Uploading a Video

```
Creator clicks "Upload" → selects video file
         │
         ▼
     🌐 Browser
         │  POST /api/videos/upload  (with file)
         ▼
     🚦 NGINX
         │
         ▼
     🎬 Video Service (Port 8002)
         │
         ├─ Save metadata to 🐘 PostgreSQL:
         │    • title, description, creator, status: "uploading"
         │
         ├─ Save raw video file to disk
         │
         └─ Publish message to 📨 Kafka topic: "video.uploaded"
              payload: { videoId, filePath, creatorId }

              ↓ Kafka delivers message to TWO workers simultaneously ↓

    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    ▼                                                      ▼
⚙️ Encoding Worker                             🖼️ Thumbnail Worker
    │                                                      │
    ├─ Run ffmpeg on video file                ├─ Extract frame at 5s
    ├─ Create 3 quality versions:              └─ Save thumbnail.jpg to disk
    │   • 360p  (low bandwidth)
    │   • 720p  (HD)
    │   • 1080p (Full HD)
    ├─ Generate HLS playlist (.m3u8)
    ├─ Update PostgreSQL status: "ready"
    └─ Publish to Kafka: "video.processed"
              │
              ▼
    🤖 Summarization Service (Port 8004)
              │
              ├─ Download audio from video
              ├─ Run OpenAI Whisper (speech → text transcript)
              ├─ Run BART AI model (text → short summary)
              ├─ Save summary to 🐘 PostgreSQL
              └─ Cache in ⚡ Redis for fast future reads
```

---

### 3️⃣ Watching a Video

```
Viewer clicks on a video to watch
         │
         ▼
     🌐 Browser (hls.js video player)
         │  GET /stream/{videoId}/manifest.m3u8
         ▼
     🚦 NGINX
         │
         ▼
     ▶️ Streaming Service (Port 8003)
         │
         ├─ Check ⚡ Redis cache for manifest (super fast!)
         │    Cache HIT?  → return it immediately ✅
         │    Cache MISS? → read from disk → store in Redis → return
         │
         └─ Browser's hls.js automatically:
              • Checks your internet speed
              • Picks the right quality (360p / 720p / 1080p)
              • Fetches video chunks (.ts files) one by one
              • Plays smoothly without buffering

SIMULTANEOUSLY → Heatmap loads:
         │  GET /api/heatmap/{videoId}
         ▼
     📊 Heatmap API (Port 8007)
         │
         └─ Read from ⚡ Redis: heatmap:{videoId}:live:*
              → Return heat scores for every 5-second segment
              → Browser renders color gradient bar under player
                 🔴 Red = most watched   🔵 Blue = least watched
```

---

### 4️⃣ The Heatmap Engine (🔥 Unique Feature)

```
Every time you watch a moment in a video, an event is sent silently:

Browser plays second 47 of a video
         │
         │  POST /api/events  { type: "PLAY", videoId: "abc", position: 47 }
         ▼
     🚦 NGINX
         │
         ▼
     📡 Event Ingestion (Port 8006)
         │
         ├─ Check rate limit in Redis (max 100 events/minute per user)
         │
         ├─ Return 202 Accepted IMMEDIATELY ← never makes you wait!
         │   (This is critical: video playback is NEVER blocked)
         │
         └─ Publish to Kafka: "viewer-interaction-events"
              │
              ▼  Kafka delivers to TWO consumers:

    ┌────────────────────────────┬────────────────────────────┐
    │                            │                            │
    ▼                            ▼                            │
🌡️ Heatmap Aggregator        🔥 Trending Service             │
    │                            │                            │
    ├─ bucket = 47 ÷ 5 = seg 9  ├─ ZINCRBY trending:videos   │
    ├─ Redis INCR live:9         │   (increment video score)  │
    ├─ Redis INCR total:9        └─ Save watch history to     │
    │                                🐘 PostgreSQL             │
    ├─ Check: is live count
    │   more than 3× the average?
    │   YES → publish "heatmap-alerts" 🚨
    │          (viral segment detected!)
    │
    └─ Every hour: flush Redis counters
         → Write snapshot to 🐘 PostgreSQL
         → Next time heatmap loads, it has history

LIVE UPDATE:
    heatmap-aggregator publishes to "heatmap-aggregated"
         │
         ▼
    📊 Heatmap API (Port 8007) receives it via SSE (Server-Sent Events)
         │
         └─ Browser heatmap updates in real time! 🎨
```

---

### 5️⃣ Trending & Recommendations

```
Every PLAY event → Kafka → Trending Service
         │
         ├─ Redis ZINCRBY: adds score to that video
         │   (think of it like upvotes, but automatic)
         │
         ├─ GET /api/trending → Redis ZREVRANGE
         │   Returns top 10 videos in milliseconds ⚡
         │
         └─ Score decays over time (older events worth less)
              → Fresh content always has a chance to trend
```

---

## 🔗 Service Communication Map

```
                         ┌──────────────────────────────────┐
                         │           BROWSER/CLIENT          │
                         └──────────────┬───────────────────┘
                                        │ HTTP
                                        ▼
                         ┌──────────────────────────────────┐
                         │         NGINX GATEWAY            │
                         └──┬───┬───┬───┬───┬───┬──────────┘
      HTTP routing          │   │   │   │   │   │
         ┌──────────────────┘   │   │   │   │   └─────────────────────┐
         │         ┌────────────┘   │   │   └──────────────┐          │
         │         │         ┌──────┘   └──────────┐        │          │
         ▼         ▼         ▼                      ▼        ▼          ▼
    ┌─────────┐ ┌────────┐ ┌──────────┐       ┌────────┐ ┌──────┐ ┌────────┐
    │  User   │ │ Video  │ │Streaming │       │Trending│ │Event │ │Heatmap │
    │ Service │ │Service │ │ Service  │       │Service │ │Ingest│ │  API   │
    └────┬────┘ └───┬────┘ └────┬─────┘       └───┬────┘ └──┬───┘ └───┬────┘
         │          │           │                  │         │         │
         │          │           │         ┌────────┘         │         │
         │    Kafka:│           │         │        Kafka:     │    SSE  │
         │  video.uploaded      │         │   viewer-events   │  stream │
         │          │           │         │                   │         │
    ┌────┴────┐      │      ┌───┴──────┐  │         ┌─────────┴─────────┐
    │  Redis  │      │      │  Redis   │  │         │  Heatmap          │
    │sessions │      │      │manifests │  │         │  Aggregator       │
    └─────────┘      │      └──────────┘  │         └─────────┬─────────┘
                     ▼                    ▼                   │
               ┌──────────────────────────────────┐           │
               │        APACHE KAFKA               │           │
               │                                  │           │
               │  video.uploaded ──────────────────┤           │
               │  video.processed ─────────────────┤           │
               │  viewer-interaction-events ────────┤           │
               │  heatmap-aggregated ───────────────┤◄──────────┘
               │  heatmap-alerts ───────────────────┤
               └──────┬──────────┬─────────────────┘
                      │          │
               ┌──────┘          └──────────┐
               ▼                            ▼
         ┌──────────┐                ┌──────────────┐
         │ Encoding │                │  Thumbnail   │
         │  Worker  │                │   Worker     │
         └────┬─────┘                └──────────────┘
              │ video.processed
              ▼
         ┌────────────────┐
         │ Summarization  │
         │   Service      │
         │ (Whisper+BART) │
         └────────────────┘
```

---

## 📦 What Runs Where (All 16 Containers)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     docker-compose up  ← ONE COMMAND                    │
│                     Starts all 16 containers automatically              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  🌐 FRONTEND (1)                                                        │
│     └─ React App (served by NGINX on port 3000 dev / 80 prod)          │
│                                                                         │
│  🚦 GATEWAY (1)                                                         │
│     └─ NGINX — port 80                                                  │
│                                                                         │
│  📦 MICROSERVICES (7)                                                   │
│     ├─ user-service        :8001  (login, register, auth)              │
│     ├─ video-service       :8002  (upload, metadata)                   │
│     ├─ streaming-service   :8003  (HLS video delivery)                 │
│     ├─ summarization-svc   :8004  (AI: Whisper + BART)                 │
│     ├─ trending-service    :8005  (leaderboard, recommendations)       │
│     ├─ event-ingestion     :8006  (viewer events, rate limiting)       │
│     └─ heatmap-api         :8007  (heatmap data, live SSE)             │
│                                                                         │
│  ⚙️  BACKGROUND WORKERS (3)                                             │
│     ├─ encoding-worker     (no port — Kafka consumer only)             │
│     ├─ thumbnail-worker    (no port — Kafka consumer only)             │
│     └─ heatmap-aggregator  (no port — Kafka consumer only)             │
│                                                                         │
│  🗄️  DATA STORES (5)                                                    │
│     ├─ PostgreSQL  :5432   (main relational database)                  │
│     ├─ Redis       :6379   (cache, sessions, counters)                 │
│     ├─ MongoDB     :27017  (logs)                                      │
│     ├─ Kafka       :9092   (event message bus)                         │
│     └─ Zookeeper   :2181   (Kafka coordinator)                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Choices Explained (Plain English)

| Technology | What It Is | Why Used Here |
|---|---|---|
| **Python + FastAPI** | Programming language + web framework | Fast, modern, easy async |
| **React + Vite** | JavaScript UI framework | Build interactive user interfaces fast |
| **NGINX** | Web server / reverse proxy | Routes requests, serves static files, rate limits |
| **PostgreSQL** | Relational database | Stores users, videos, summaries — structured data |
| **Redis** | In-memory data store | Blazing fast: sessions, counters, leaderboards |
| **MongoDB** | Document database | Flexible logs that auto-delete |
| **Apache Kafka** | Message queue/event bus | Decouples services; nothing is lost; handles traffic spikes |
| **ffmpeg** | Video processing tool | Converts uploaded videos to streaming format |
| **OpenAI Whisper** | AI speech-to-text | Transcribes video audio to text (runs locally, no API cost) |
| **BART (HuggingFace)** | AI text summarization | Turns transcript into a short readable summary |
| **HLS** | HTTP Live Streaming protocol | Adaptive quality video that adjusts to internet speed |
| **hls.js** | JavaScript HLS player | Plays HLS video in any browser |
| **Docker Compose** | Container orchestration | One command starts the entire platform |
| **Alembic** | Database migration tool | Manages database schema changes safely |
| **bcrypt** | Password hashing | Passwords are never stored in plain text |

---

## 🗄️ Database Schema (What Data Is Stored)

### PostgreSQL Tables

```
┌─────────────────────────────────────────────────────┐
│  users                        (owner: user-service) │
│  ─────────────────────────────────────────────────  │
│  id · email · hashed_password · name · created_at   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  videos                      (owner: video-service) │
│  ─────────────────────────────────────────────────  │
│  id · title · description · creator_id              │
│  status: uploading→encoding→ready                   │
│  file_path · thumbnail_path · created_at            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  video_summaries    (owner: summarization-service)  │
│  ─────────────────────────────────────────────────  │
│  id · video_id · transcript · summary · created_at  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  watch_history           (owner: trending-service)  │
│  ─────────────────────────────────────────────────  │
│  user_id · video_id · watched_at · duration_watched │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  viewer_events        (owner: heatmap-aggregator)   │
│  partitioned by month for fast cleanup              │
│  ─────────────────────────────────────────────────  │
│  id · video_id · user_id · event_type               │
│  position_seconds · created_at                      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  video_heatmap_snapshots  (owner: heatmap-aggregator)│
│  hourly flush of Redis counters                     │
│  ─────────────────────────────────────────────────  │
│  id · video_id · segment_index · view_count         │
│  snapshot_time                                      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  viral_segment_alerts     (owner: heatmap-aggregator)│
│  spike detection log                                │
│  ─────────────────────────────────────────────────  │
│  id · video_id · segment_index · spike_ratio        │
│  detected_at                                        │
└─────────────────────────────────────────────────────┘
```

### Redis Keys (Fast Cache)

```
session:{session-id}          → user's login session (expires 24h)
heatmap:{videoId}:live:{seg}  → live viewer count for 5-sec segment
heatmap:{videoId}:total:{seg} → all-time views for segment
heatmap:{videoId}:baseline    → average used for spike detection
trending:videos               → sorted set: videoId → score
summary:{videoId}             → cached AI summary
stream:manifest:{videoId}     → cached HLS playlist file
ratelimit:events:{sessionId}  → rate limit counter (100/min)
```

---

## 🔥 The Heatmap Engine — Deep Dive

This is the **most unique feature** of the platform.

### The Concept

Imagine watching a 10-minute documentary. Some moments are skipped by everyone. Others get rewatched again and again — perhaps a shocking reveal, a funny moment, or a key insight. The heatmap tells you **exactly which moments** those are.

```
Video Timeline:  ──────────────────────────────────────────────
Heatmap color:   🔵🔵🔵🟢🟡🟠🔴🔴🔴🟠🟡🟢🔵🔵🔵🔵🔵🔵🔵🔵
                                ↑ Most watched moment
```

### How It Works Technically

```
Every 5 seconds of video = 1 "bucket" (segment)

A 10-minute video = 120 buckets

Bucket math: position ÷ 5 = bucket number
  Second 0-4   → Bucket 0
  Second 5-9   → Bucket 1
  Second 47    → Bucket 9
  Second 297   → Bucket 59

Every PLAY event:
  Redis: INCR heatmap:{videoId}:live:{bucketNumber}
         INCR heatmap:{videoId}:total:{bucketNumber}

Every hour:
  Flush Redis → PostgreSQL snapshot (persistent record)

Spike detection:
  If bucket count > 3× average → "viral segment" alert 🚨
```

---

## 📡 Kafka Topics — The Messaging System

Kafka is like the **internal mail room** of the platform. Services drop messages, and other services pick them up. Nothing is lost even if a service is temporarily down.

```
┌─────────────────────────────────────────────────────────────────┐
│                       KAFKA TOPICS                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📼 video.uploaded          (3 lanes / partitions)              │
│     Producer:  video-service (when creator uploads)             │
│     Consumers: encoding-worker + thumbnail-worker               │
│                                                                  │
│  ✅ video.processed         (3 lanes / partitions)              │
│     Producer:  encoding-worker (when HLS files are ready)       │
│     Consumers: summarization-service                            │
│                                                                  │
│  👁️  viewer-interaction-events (12 lanes / partitions)          │
│     Producer:  event-ingestion (every view/pause/seek event)    │
│     Consumers: heatmap-aggregator + trending-service            │
│                                                                  │
│  🌡️  heatmap-aggregated      (6 lanes / partitions)             │
│     Producer:  heatmap-aggregator                               │
│     Consumers: heatmap-api (live SSE updates to browser)        │
│                                                                  │
│  🚨 heatmap-alerts          (3 lanes / partitions)              │
│     Producer:  heatmap-aggregator (spike detected)              │
│     Consumers: (notifications, future features)                 │
│                                                                  │
│  ℹ️  Why 12 lanes for viewer events?                            │
│     High traffic — many viewers at once. More lanes = more      │
│     consumers processing in parallel = no bottleneck.           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Design

```
┌─────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Password Security                                   │
│     └─ bcrypt hashing — passwords never stored raw      │
│                                                         │
│  2. Session Authentication                              │
│     └─ Random session ID in HttpOnly cookie             │
│        (JavaScript cannot read it — XSS protection)    │
│        └─ Redis stores: session:{id} → userId           │
│           Expires automatically after 24 hours          │
│                                                         │
│  3. Rate Limiting                                       │
│     └─ NGINX: global request rate limit                 │
│     └─ Event Ingestion: 100 viewer events/minute/user   │
│                                                         │
│  4. Ownership Checks                                    │
│     └─ Only the creator can delete/edit their video     │
│     └─ Only the creator can see their video's heatmap   │
│                                                         │
│  5. No Service-to-Service HTTP                          │
│     └─ Services communicate ONLY through Kafka + Redis  │
│        (no internal REST calls = harder to exploit)     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗️ Build Phases (How the Project Is Built)

The project is built in **10 phases**, in order of dependencies:

```
Phase 1: Infrastructure & Skeleton
  └─ Docker Compose, NGINX, shared Python module, database setup

Phase 2: User Service
  └─ Register, login, logout, session management

Phase 3: Video Service
  └─ Upload, metadata, Kafka producer

Phase 4: Processing Pipeline
  └─ Encoding worker (ffmpeg → HLS)
  └─ Thumbnail worker (ffmpeg → image)

Phase 5: Streaming Service
  └─ HLS manifest serving, Redis cache, segment delivery

Phase 6: AI Summarization
  └─ Whisper transcription, BART summary, Kafka consumer

Phase 7: Trending & Recommendations
  └─ Redis sorted set, leaderboard, watch history

Phase 8: Heatmap Engine (THE UNIQUE FEATURE)
  8a → Event Ingestion Service
  8b → Heatmap Aggregator Worker
  8c → Heatmap API

Phase 9: Frontend (React)
  └─ UI, video player, heatmap bar, trending feed

Phase 10: Integration & Documentation
  └─ End-to-end tests, final polish, README
```

---

## 📊 Project Summary Card

| Item | Detail |
|---|---|
| **Platform type** | Distributed video streaming (YouTube/Netflix-style) |
| **Total services** | 10 microservices + 3 workers + NGINX + frontend |
| **Total containers** | 16 (one `docker-compose up` starts all) |
| **Backend language** | Python 3.11 + FastAPI |
| **Frontend** | React 18 + Vite + hls.js + recharts |
| **Databases** | PostgreSQL + Redis + MongoDB |
| **Message broker** | Apache Kafka (5 topics) |
| **AI features** | Whisper (speech→text) + BART (summarization) |
| **Video processing** | ffmpeg → HLS adaptive bitrate (360p/720p/1080p) |
| **Auth method** | Session-based with Redis (HttpOnly cookie) |
| **Unique feature** | Real-time Viewer Behavior Heatmap Engine |
| **Deployment** | Docker Compose (single command) |

---

> 📄 *Generated from `docs/COPILOT.md` and `docs/HLD.md`*
> 🏗️ *Implementation status: All 10 phases pending — ready to build*

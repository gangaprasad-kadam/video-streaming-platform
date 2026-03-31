# 🗄️ Database Design

## Overview

The platform uses a **polyglot persistence** strategy — different databases for different data characteristics:

| Database | Role | Used By |
|---|---|---|
| **PostgreSQL** | Primary relational store — users, videos, heatmaps, history | All services |
| **Redis** | Ephemeral cache, sessions, counters, pub/sub | All services |
| **MongoDB** | Append-only logs, unstructured processing audit trails | Processing workers, error tracking |
| **Kafka** | Durable event log (not a DB, but treated as source of truth for events) | All services |

---

## 1. PostgreSQL — Relational Schema

### 1.1 Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         POSTGRESQL ER DIAGRAM                                │
└──────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐
  │     USERS       │
  ├─────────────────┤
  │ PK id (UUID)    │◄──────────────────────────────────────────┐
  │    username     │                                           │
  │    email        │◄────────────────┐                        │
  │    password_hash│                 │                        │
  │    created_at   │                 │                        │
  │    updated_at   │                 │                        │
  └────────┬────────┘                 │                        │
           │ 1                        │                        │
           │ creates                  │                        │
           │ many                     │                        │
           ▼ N                        │                        │
  ┌─────────────────┐                 │                        │
  │     VIDEOS      │                 │                        │
  ├─────────────────┤                 │                        │
  │ PK id (UUID)    │◄────────────────│────────────────────────│──────┐
  │ FK creator_id ──┼─────────────────┘                        │      │
  │    title        │                                           │      │
  │    description  │                                           │      │
  │    file_path    │                                           │      │
  │    hls_path     │                                           │      │
  │    thumbnail_path│                                          │      │
  │    duration     │                                           │      │
  │    status       │◄── uploading|processing|ready|failed      │      │
  │    file_size    │                                           │      │
  │    mime_type    │                                           │      │
  │    created_at   │                                           │      │
  │    updated_at   │                                           │      │
  └──────┬──────────┘                                           │      │
         │ 1                                                    │      │
         ├─────────────────────────────────────────┐           │      │
         │ has 0..1                                 │ has many  │      │
         ▼                                          ▼           │      │
  ┌──────────────────┐                 ┌──────────────────┐    │      │
  │  VIDEO_SUMMARIES │                 │   WATCH_HISTORY  │    │      │
  ├──────────────────┤                 ├──────────────────┤    │      │
  │ PK id (UUID)     │                 │ PK id (BIGSERIAL)│    │      │
  │ FK video_id ─────┼─────────────────┼▶FK video_id      │    │      │
  │    transcript    │                 │ FK user_id ──────┼────┘      │
  │    summary       │                 │    watched_at    │           │
  │    key_moments   │                 │    watch_pct     │           │
  │    (JSONB)       │                 │ UNIQUE(user,vid) │           │
  │    whisper_model │                 └──────────────────┘           │
  │    processing_ms │                                                 │
  │    created_at    │                                                 │
  └──────────────────┘                                                 │
                                                                       │
         ┌─────────────────────────────────────────────────────────────┘
         │ has many
         ▼
  ┌──────────────────────┐          ┌──────────────────────────┐
  │   VIEWER_EVENTS      │          │  VIDEO_HEATMAP_SNAPSHOTS │
  │   (partitioned)      │          ├──────────────────────────┤
  ├──────────────────────┤          │ PK id (BIGSERIAL)        │
  │ PK id (BIGSERIAL)    │          │ FK video_id ─────────────┼──▶ VIDEOS
  │ FK video_id          │          │    segment_id            │
  │ FK user_id (nullable)│          │    segment_start         │
  │    session_id (UUID) │          │    segment_end           │
  │    event_type        │          │    rewind_count          │
  │    video_ts          │          │    pause_count           │
  │    seek_from         │          │    seek_to_count         │
  │    client_time       │          │    skip_count            │
  │    ingested_at       │          │    total_viewers         │
  └──────────────────────┘          │    snapshot_hour         │
   Partitioned by ingested_at       │ UNIQUE(video,seg,hour)   │
   (range partition, monthly)       └──────────────────────────┘

  ┌───────────────────────┐
  │  VIRAL_SEGMENT_ALERTS │
  ├───────────────────────┤
  │ PK id (BIGSERIAL)     │
  │ FK video_id ──────────┼──▶ VIDEOS
  │    segment_id         │
  │    metric             │
  │    value              │
  │    baseline           │
  │    sigma              │
  │    alerted_at         │
  └───────────────────────┘
```

---

### 1.2 Complete Table Definitions

#### `users`

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(60) NOT NULL,           -- bcrypt (always 60 chars)
    created_at    TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

#### `videos`

```sql
CREATE TYPE video_status AS ENUM ('uploading', 'processing', 'ready', 'failed');

CREATE TABLE videos (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id       UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    file_path        TEXT         NOT NULL,   -- /media/uploads/{id}.mp4
    hls_path         TEXT,                    -- /media/hls/{id}/index.m3u8 (set after encoding)
    thumbnail_path   TEXT,                    -- /media/thumbnails/{id}.jpg (set after thumb gen)
    duration         DECIMAL(10,2),           -- seconds (set after encoding)
    status           video_status NOT NULL DEFAULT 'uploading',
    file_size_bytes  BIGINT,
    mime_type        VARCHAR(50),
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_videos_creator_id ON videos(creator_id);
CREATE INDEX idx_videos_status     ON videos(status);
CREATE INDEX idx_videos_created_at ON videos(created_at DESC);
```

#### `video_summaries`

```sql
CREATE TABLE video_summaries (
    id             UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id       UUID      UNIQUE NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    transcript     TEXT,                    -- full Whisper transcript
    summary        TEXT      NOT NULL,      -- BART-generated summary
    key_moments    JSONB,
    -- [{ "timestamp": 42.0, "label": "Introduction to recursion" }]
    whisper_model  VARCHAR(20) DEFAULT 'base',
    processing_ms  INTEGER,                 -- pipeline duration in ms
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- key_moments is queried by video player for chapter markers
CREATE INDEX idx_summaries_video_id ON video_summaries(video_id);
```

`key_moments` JSONB structure:
```json
[
  { "timestamp": 42.0,  "label": "Introduction" },
  { "timestamp": 180.5, "label": "Live coding demo" },
  { "timestamp": 320.0, "label": "Common mistakes" }
]
```

#### `watch_history`

```sql
CREATE TABLE watch_history (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id    UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    watched_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    watch_pct   DECIMAL(5,2),   -- 0.00 to 100.00 (% of video watched)
    CONSTRAINT uq_user_video UNIQUE (user_id, video_id)
    -- ON CONFLICT DO UPDATE — update watched_at and watch_pct on re-watch
);

CREATE INDEX idx_watch_history_user    ON watch_history(user_id, watched_at DESC);
CREATE INDEX idx_watch_history_video   ON watch_history(video_id);
```

#### `viewer_events` (partitioned)

```sql
CREATE TABLE viewer_events (
    id           BIGSERIAL,
    video_id     UUID        NOT NULL,
    user_id      UUID,                      -- NULL for anonymous viewers
    session_id   UUID        NOT NULL,
    event_type   VARCHAR(20) NOT NULL,
    -- REWIND | PAUSE | SEEK | SKIP | PLAY | SPEED_CHANGE | BUFFER
    video_ts     DECIMAL(10,3) NOT NULL,    -- position in video (seconds)
    seek_from    DECIMAL(10,3),             -- only for SEEK events
    client_time  BIGINT      NOT NULL,      -- unix timestamp from browser
    ingested_at  TIMESTAMP   NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (ingested_at);

-- Monthly partitions (auto-created by application or pg_partman)
CREATE TABLE viewer_events_2026_03 PARTITION OF viewer_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE viewer_events_2026_04 PARTITION OF viewer_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Indexes on partitioned table
CREATE INDEX idx_viewer_events_video   ON viewer_events(video_id, ingested_at DESC);
CREATE INDEX idx_viewer_events_session ON viewer_events(session_id);
CREATE INDEX idx_viewer_events_type    ON viewer_events(event_type);
```

#### `video_heatmap_snapshots`

```sql
CREATE TABLE video_heatmap_snapshots (
    id             BIGSERIAL   PRIMARY KEY,
    video_id       UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    segment_id     INTEGER     NOT NULL,        -- bucket index (0, 1, 2 ...)
    segment_start  DECIMAL(10,3) NOT NULL,      -- e.g., 140.000 seconds
    segment_end    DECIMAL(10,3) NOT NULL,      -- e.g., 145.000 seconds
    rewind_count   INTEGER     NOT NULL DEFAULT 0,
    pause_count    INTEGER     NOT NULL DEFAULT 0,
    seek_to_count  INTEGER     NOT NULL DEFAULT 0,
    skip_count     INTEGER     NOT NULL DEFAULT 0,
    total_viewers  INTEGER     NOT NULL DEFAULT 0, -- unique sessions in this window
    snapshot_hour  TIMESTAMP   NOT NULL,           -- truncated to hour
    created_at     TIMESTAMP   NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_heatmap_snapshot UNIQUE (video_id, segment_id, snapshot_hour)
);

CREATE INDEX idx_heatmap_video_hour ON video_heatmap_snapshots(video_id, snapshot_hour DESC);
CREATE INDEX idx_heatmap_segment    ON video_heatmap_snapshots(video_id, segment_id);
```

#### `viral_segment_alerts`

```sql
CREATE TABLE viral_segment_alerts (
    id          BIGSERIAL   PRIMARY KEY,
    video_id    UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    segment_id  INTEGER     NOT NULL,
    metric      VARCHAR(20) NOT NULL,   -- e.g., REWIND_RATE
    value       DECIMAL     NOT NULL,   -- actual observed value
    baseline    DECIMAL     NOT NULL,   -- expected mean
    sigma       DECIMAL     NOT NULL,   -- how many std deviations above mean
    alerted_at  TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_viral_alerts_video ON viral_segment_alerts(video_id, alerted_at DESC);
```

---

### 1.3 Table Relationship Summary

```
users (1) ────────── (N) videos
  │                         │
  │ (N)               (0..1)│(1)        (N)
  │                         │
watch_history        video_summaries   video_heatmap_snapshots
  │(N)    (N)│              │                  │(N)
  │          │              │                  │
  ▼          ▼              ▼                  ▼
videos     users          videos            videos
                                     viral_segment_alerts (N)
                                              │(N)
                                              ▼
                                           videos

viewer_events (N) ─── (partitioned by date, no FK enforced for performance)
```

### 1.4 Cardinalities

| Relationship | Type | Notes |
|---|---|---|
| User → Videos | 1 : N | One creator, many videos |
| Video → Summary | 1 : 0..1 | Generated asynchronously after processing |
| User ↔ Video (watch_history) | N : M | Many users watch many videos |
| Video → Heatmap Snapshots | 1 : N | Many hourly snapshots per video |
| Video → Viewer Events | 1 : N | Raw event log, partitioned |
| Video → Viral Alerts | 1 : N | Multiple alerts possible per video |

---

## 2. Redis — Key Design

### 2.1 Key Map

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           REDIS KEY DESIGN                                 │
├─────────────────────────────────────┬──────────────┬───────────────────────┤
│ Key Pattern                         │ Type         │ TTL                   │
├─────────────────────────────────────┼──────────────┼───────────────────────┤
│ session:{sessionId}                 │ String       │ 86400s (24h, sliding) │
│ stream:manifest:{videoId}           │ String       │ 300s (5min)           │
│ summary:{videoId}                   │ String (JSON)│ 3600s (1h)            │
│ trending:videos                     │ Sorted Set   │ No TTL (persistent)   │
│ heatmap:{videoId}:live:{segmentId}  │ Hash         │ 600s (10min)          │
│ heatmap:{videoId}:total:{segmentId} │ Hash         │ 604800s (7 days)      │
│ heatmap:{videoId}:summary           │ Hash         │ 3600s (1h)            │
│ heatmap:{videoId}:baseline:{segId}  │ Hash         │ No TTL (persistent)   │
│ ratelimit:events:{sessionId}        │ String (int) │ 60s (1min window)     │
│ heatmap-updates:{videoId}           │ Pub/Sub      │ N/A (channel)         │
└─────────────────────────────────────┴──────────────┴───────────────────────┘
```

### 2.2 Detailed Key Descriptions

#### Sessions
```
Key   : session:{sessionId}
Type  : String
Value : userId (UUID string)
TTL   : 86400s — reset on each authenticated request (sliding expiry)
Owner : User Service

Example:
  SET session:f3a9b1c2-... "a1b2c3d4-..." EX 86400
```

#### HLS Manifest Cache
```
Key   : stream:manifest:{videoId}
Type  : String
Value : full .m3u8 manifest content
TTL   : 300s — short TTL, re-read from disk on miss
Owner : Streaming Service

Example:
  SET stream:manifest:vid-uuid "#EXTM3U\n#EXT-X-VERSION:3\n..." EX 300
```

#### Summary Cache
```
Key   : summary:{videoId}
Type  : String (JSON)
Value : { "summary": "...", "keyMoments": [...] }
TTL   : 3600s
Owner : Summarization Service

Example:
  SET summary:vid-uuid '{"summary":"This video...","keyMoments":[...]}' EX 3600
```

#### Trending Sorted Set
```
Key    : trending:videos
Type   : Sorted Set
Member : videoId (UUID string)
Score  : cumulative weighted interaction score
TTL    : None (persistent, scores decay hourly via background job)
Owner  : Trending Service

Commands used:
  ZINCRBY trending:videos 3.0 "vid-uuid"     ← on REWIND event
  ZINCRBY trending:videos 1.0 "vid-uuid"     ← on PLAY event
  ZREVRANGE trending:videos 0 9 WITHSCORES   ← top 10

Visual:
  trending:videos = {
    "vid-aaa": 4821.5,   ← rank 1
    "vid-bbb": 3102.0,   ← rank 2
    "vid-ccc": 1890.5,   ← rank 3
    ...
  }
```

#### Heatmap Live Counter
```
Key   : heatmap:{videoId}:live:{segmentId}
Type  : Hash
Fields: { REWIND: int, PAUSE: int, SEEK: int, SKIP: int, PLAY: int }
TTL   : 600s (10min) — represents the 5-min sliding window + buffer
Owner : Heatmap Aggregator

Example:
  HINCRBY heatmap:vid-uuid:live:28 REWIND 1
  HGETALL heatmap:vid-uuid:live:28
  → { REWIND: 45, PAUSE: 12, SEEK: 8, SKIP: 3 }
```

#### Heatmap Total Counter
```
Key   : heatmap:{videoId}:total:{segmentId}
Type  : Hash
Fields: { REWIND: int, PAUSE: int, SEEK: int, SKIP: int, PLAY: int }
TTL   : 604800s (7 days) — flushed to PostgreSQL hourly before expiry
Owner : Heatmap Aggregator

Segment IDs: segmentId = floor(videoTimestamp / 5)
  videoTs=0    → segId=0   (0s–5s)
  videoTs=142  → segId=28  (140s–145s)
  videoTs=300  → segId=60  (300s–305s)
```

#### Heatmap Baseline (for Viral Detection)
```
Key   : heatmap:{videoId}:baseline:{segmentId}
Type  : Hash
Fields: { mean: float, stddev: float, sample_count: int }
TTL   : No TTL (recalculated weekly)
Owner : Heatmap Aggregator

Used by viral detector:
  sigma = (current_rewind - mean) / stddev
  if sigma > 3.0 → publish heatmap-alerts Kafka event
```

#### Rate Limit Token Bucket
```
Key   : ratelimit:events:{sessionId}
Type  : String (integer counter)
Value : number of events in current 60s window
TTL   : 60s (auto-reset after window)
Owner : Event Ingestion Service

Logic:
  INCR ratelimit:events:{sid}     → increment counter
  If result == 1: EXPIRE key 60  → start the window on first event
  If result > 100: return 429 Too Many Requests
```

### 2.3 Redis Memory Estimate

```
Assumptions:
  • 10,000 active videos
  • 200 segments per video (avg 1000s ÷ 5s)
  • Each hash field = ~50 bytes

heatmap:*:live:*   = 10,000 × 200 × 50B = ~100MB
heatmap:*:total:*  = 10,000 × 200 × 50B = ~100MB
sessions           = 50,000 users × 100B = ~5MB
trending:videos    = 10,000 × 50B        = ~0.5MB
manifest cache     = 1,000 × 1KB         = ~1MB

Total estimated: ~206MB  ← well within Redis defaults
```

---

## 3. MongoDB — Collections

MongoDB is used for **append-only logs** where the schema is flexible and query patterns are simple (insert + recent-N lookup).

### 3.1 Collections

#### `processing_logs`

Audit trail for every video processing job (encoding, thumbnail generation).

```javascript
// Collection: processing_logs
{
  _id: ObjectId,
  videoId: "uuid-string",
  workerType: "encoding" | "thumbnail",
  status: "started" | "completed" | "failed",
  inputPath: "/media/uploads/uuid.mp4",
  outputPath: "/media/hls/uuid/index.m3u8",
  durationMs: 45230,
  errorMessage: null,            // populated on failure
  ffmpegCommand: "ffmpeg -i ...", // full command for debugging
  startedAt: ISODate("2026-03-31T12:00:00Z"),
  completedAt: ISODate("2026-03-31T12:00:45Z")
}

// Indexes:
db.processing_logs.createIndex({ videoId: 1, startedAt: -1 })
db.processing_logs.createIndex({ status: 1 })
db.processing_logs.createIndex({ startedAt: 1 }, { expireAfterSeconds: 2592000 })
// ↑ Auto-delete logs older than 30 days (TTL index)
```

#### `error_logs`

Centralized error collection across all microservices.

```javascript
// Collection: error_logs
{
  _id: ObjectId,
  service: "video-service" | "encoding-worker" | "heatmap-aggregator" | ...,
  level: "ERROR" | "WARN" | "CRITICAL",
  message: "Failed to publish Kafka event",
  stack: "Traceback (most recent call last):\n  ...",
  context: {
    videoId: "uuid",          // optional — any relevant context
    userId: "uuid",
    endpoint: "POST /videos/upload",
    requestId: "uuid"
  },
  occurredAt: ISODate("2026-03-31T12:00:00Z")
}

// Indexes:
db.error_logs.createIndex({ service: 1, occurredAt: -1 })
db.error_logs.createIndex({ level: 1, occurredAt: -1 })
db.error_logs.createIndex({ occurredAt: 1 }, { expireAfterSeconds: 604800 })
// ↑ Auto-delete logs older than 7 days
```

### 3.2 Why MongoDB for Logs?

```
✅ Schema-free — different services log different context fields
✅ TTL indexes — automatic log rotation (no cron jobs needed)
✅ Append-only writes — MongoDB's strength
✅ Simple queries — always recent-N or filter by service/level
❌ Would be overkill for structured relational queries
```

---

## 4. Kafka — Event Schema Reference

Kafka is the event backbone. Each topic acts as a durable, ordered log.

### 4.1 Topic Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         KAFKA TOPICS                                     │
├────────────────────────────┬─────────┬────────────┬──────────────────────┤
│ Topic                      │ Parts   │ Retention  │ Partition Key        │
├────────────────────────────┼─────────┼────────────┼──────────────────────┤
│ video.uploaded             │ 3       │ 7 days     │ videoId              │
│ video.processed            │ 3       │ 7 days     │ videoId              │
│ viewer-interaction-events  │ 12      │ 3 days     │ videoId              │
│ heatmap-aggregated         │ 6       │ 1 day      │ videoId              │
│ heatmap-alerts             │ 3       │ 30 days    │ videoId              │
└────────────────────────────┴─────────┴────────────┴──────────────────────┘
```

### 4.2 Event Schemas

#### `video.uploaded`
```json
{
  "videoId":    "uuid",
  "creatorId":  "uuid",
  "filePath":   "/media/uploads/uuid.mp4",
  "mimeType":   "video/mp4",
  "title":      "My Video Title",
  "uploadedAt": "2026-03-31T12:00:00Z"
}
```
**Produced by:** Video Service  
**Consumed by:** Encoding Worker (group: `encoding-worker-group`), Thumbnail Worker (group: `thumbnail-worker-group`)

---

#### `video.processed`
```json
{
  "videoId":      "uuid",
  "creatorId":    "uuid",
  "hlsPath":      "/media/hls/uuid/index.m3u8",
  "thumbnailPath":"/media/thumbnails/uuid.jpg",
  "duration":     542.3,
  "processedAt":  "2026-03-31T12:05:00Z"
}
```
**Produced by:** Encoding Worker  
**Consumed by:** Summarization Service (group: `summarization-service-group`)

---

#### `viewer-interaction-events`
```json
{
  "videoId":    "uuid",
  "userId":     "uuid | null",
  "sessionId":  "uuid",
  "eventType":  "REWIND | PAUSE | SEEK | SKIP | PLAY | SPEED_CHANGE | BUFFER",
  "videoTs":    142.5,
  "seekFrom":   null,
  "clientTime": 1711882140,
  "ingestedAt": "2026-03-31T12:30:00Z"
}
```
**Produced by:** Event Ingestion Service  
**Consumed by:** Heatmap Aggregator (group: `heatmap-aggregator-group`), Trending Service (group: `trending-service-group`)

---

#### `heatmap-aggregated`
```json
{
  "videoId":   "uuid",
  "segmentId": 28,
  "window":    "live | hourly",
  "counts":    { "REWIND": 45, "PAUSE": 12, "SEEK": 8, "SKIP": 3 },
  "updatedAt": "2026-03-31T12:30:05Z"
}
```
**Produced by:** Heatmap Aggregator  
**Consumed by:** Heatmap API (SSE push trigger)

---

#### `heatmap-alerts`
```json
{
  "videoId":   "uuid",
  "creatorId": "uuid",
  "segmentId": 28,
  "metric":    "REWIND_RATE",
  "value":     0.67,
  "baseline":  0.12,
  "sigma":     4.2,
  "alertedAt": "2026-03-31T12:30:10Z"
}
```
**Produced by:** Heatmap Aggregator  
**Consumed by:** (Notification Service — future)

---

## 5. Full Data Store Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WHERE EACH SERVICE READS/WRITES                      │
├──────────────────────┬────────────┬──────────┬───────────┬──────────────────┤
│ Service              │ PostgreSQL │ Redis    │ MongoDB   │ Kafka            │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ User Service         │ users (RW) │ session  │ error_logs│ —                │
│                      │            │ (RW)     │ (W)       │                  │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Video Service        │ videos (RW)│ —        │ error_logs│ video.uploaded(W)│
│                      │            │          │ (W)       │                  │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Encoding Worker      │ videos (W) │ —        │ processing│ video.uploaded(R)│
│                      │ (status)   │          │ _logs (W) │ video.processed  │
│                      │            │          │           │ (W)              │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Thumbnail Worker     │ videos (W) │ —        │ processing│ video.uploaded(R)│
│                      │ (thumb)    │          │ _logs (W) │                  │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Streaming Service    │ videos (R) │ manifest │ —         │ —                │
│                      │ (hls_path) │ cache(RW)│           │                  │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Summarization Svc    │ summaries  │ summary  │ —         │ video.processed  │
│                      │ (RW)       │ cache(W) │           │ (R)              │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Trending Service     │ watch_hist │ trending │ —         │ viewer-interact  │
│                      │ (R)        │ (RW)     │           │ ion-events (R)   │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Event Ingestion      │ —          │ ratelimit│ —         │ viewer-interact  │
│                      │            │ (RW)     │           │ ion-events (W)   │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Heatmap Aggregator   │ heatmap_   │ heatmap  │ —         │ viewer-interact  │
│                      │ snapshots  │ live/    │           │ ion-events (R)   │
│                      │ (W)        │ total/   │           │ heatmap-alerts   │
│                      │ viewer_    │ baseline │           │ (W)              │
│                      │ events (W) │ (RW)     │           │ heatmap-         │
│                      │            │          │           │ aggregated (W)   │
├──────────────────────┼────────────┼──────────┼───────────┼──────────────────┤
│ Heatmap API          │ heatmap_   │ heatmap  │ —         │ heatmap-         │
│                      │ snapshots  │ live/    │           │ aggregated (R)   │
│                      │ (R)        │ total(R) │           │                  │
└──────────────────────┴────────────┴──────────┴───────────┴──────────────────┘
```

---

## 6. Data Lifecycle & Retention

```
viewer_events (PostgreSQL, partitioned)
  → kept 90 days, then partition dropped

video_heatmap_snapshots (PostgreSQL)
  → kept indefinitely (creator analytics)

processing_logs (MongoDB)
  → TTL index: auto-deleted after 30 days

error_logs (MongoDB)
  → TTL index: auto-deleted after 7 days

heatmap:*:live:* (Redis)
  → TTL 10 minutes (sliding window cache)

heatmap:*:total:* (Redis)
  → TTL 7 days, flushed to PostgreSQL hourly

session:* (Redis)
  → TTL 24 hours, sliding (reset on each request)

Kafka topics
  → viewer-interaction-events: 3-day retention
  → video.*: 7-day retention
  → heatmap-alerts: 30-day retention
```

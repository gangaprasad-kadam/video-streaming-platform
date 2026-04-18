# Database Design

Polyglot persistence: **PostgreSQL** (relational), **Redis** (cache/sessions), **Kafka** (events), **MongoDB** (logs).

---

## 1. PostgreSQL Schema

### ER Diagram

```
  ┌─────────────────┐
  │     USERS       │
  ├─────────────────┤
  │ PK id (UUID)    │◄──────────────────────────┐
  │    username      │                           │
  │    email         │                           │
  │    password_hash │                           │
  │    created_at    │                           │
  │    updated_at    │                           │
  └────────┬────────┘                           │
           │ 1:N                                │
           ▼                                    │
  ┌─────────────────┐          ┌────────────────┴───┐
  │     VIDEOS      │          │   WATCH_HISTORY    │
  ├─────────────────┤          │   [Planned]        │
  │ PK id (UUID)    │◄────┐    ├────────────────────┤
  │ FK creator_id   │     │    │ FK user_id → users │
  │    title        │     └────│ FK video_id        │
  │    description  │          │    watched_at      │
  │    file_path    │          │    watch_pct       │
  │    hls_path     │          └────────────────────┘
  │    thumbnail_path│
  │    duration     │     ┌────────────────────┐
  │    status       │     │ VIDEO_SUMMARIES    │
  │    file_size    │     │ [Planned]          │
  │    mime_type    │     ├────────────────────┤
  │    created_at   │     │ FK video_id        │
  │    updated_at   │     │    transcript      │
  └─────────────────┘     │    summary         │
                          │    key_moments     │
                          └────────────────────┘
```

### `users` — Active

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(60) NOT NULL,           -- bcrypt
    created_at    TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

### `videos` — Active

```sql
CREATE TYPE video_status AS ENUM ('uploading', 'processing', 'ready', 'failed');

CREATE TABLE videos (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id       UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            VARCHAR(255) NOT NULL,
    description      TEXT,
    file_path        TEXT         NOT NULL,
    hls_path         TEXT,
    thumbnail_path   TEXT,
    duration         DECIMAL(10,2),
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

### Planned Tables

#### `video_summaries` — Planned (Summarization Service)

```sql
CREATE TABLE video_summaries (
    id             UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id       UUID      UNIQUE NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    transcript     TEXT,
    summary        TEXT      NOT NULL,
    key_moments    JSONB,    -- [{ "timestamp": 42.0, "label": "..." }]
    whisper_model  VARCHAR(20) DEFAULT 'base',
    processing_ms  INTEGER,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);
```

#### `watch_history` — Planned (Trending Service)

```sql
CREATE TABLE watch_history (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id    UUID        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    watched_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    watch_pct   DECIMAL(5,2),
    CONSTRAINT uq_user_video UNIQUE (user_id, video_id)
);
```

#### `viewer_events` — Planned (Heatmap Aggregator)

Partitioned by `ingested_at` (monthly ranges). Stores raw playback events (REWIND, PAUSE, SEEK, etc.).

#### `video_heatmap_snapshots` — Planned (Heatmap Aggregator)

Hourly aggregated heatmap data per video segment. Unique on `(video_id, segment_id, snapshot_hour)`.

#### `viral_segment_alerts` — Planned (Heatmap Aggregator)

Alerts when a segment's rewind/pause rate exceeds 3σ above baseline.

---

## 2. Redis Key Patterns

| Key Pattern                          | Type        | TTL          | Status   |
| ------------------------------------ | ----------- | ------------ | -------- |
| `session:{sessionId}`                | String      | 86400s (24h) | **Active** |
| `stream:manifest:{videoId}`          | String      | 300s (5min)  | **Active** |
| `summary:{videoId}`                  | String/JSON | 3600s (1h)   | Planned  |
| `trending:videos`                    | Sorted Set  | Persistent   | Planned  |
| `heatmap:{videoId}:live:{segId}`     | Hash        | 600s (10min) | Planned  |
| `heatmap:{videoId}:total:{segId}`    | Hash        | 7 days       | Planned  |
| `heatmap:{videoId}:baseline:{segId}` | Hash        | Persistent   | Planned  |
| `ratelimit:events:{sessionId}`       | String/int  | 60s          | Planned  |

### Active Keys

```
session:{sessionId}
  Value: userId (UUID)
  Sliding TTL reset on each authenticated request.

stream:manifest:{videoId}
  Value: .m3u8 manifest content
  Short cache; re-read from disk on miss.
```

### Planned Keys (brief)

- **trending:videos** — Sorted set; scores represent weighted interaction counts. Decayed hourly.
- **heatmap:\*** — Live/total counters per 5-second video segment. Flushed to PostgreSQL hourly.
- **ratelimit:events:\*** — 60s sliding window, max 100 events/min per session.

---

## 3. Kafka Topics & Event Schemas

| Topic                       | Partitions | Retention | Key       | Status   |
| --------------------------- | ---------- | --------- | --------- | -------- |
| `video.uploaded`            | 3          | 7 days    | videoId   | **Active** |
| `video.processed`           | 3          | 7 days    | videoId   | **Active** |
| `viewer-interaction-events` | 12         | 3 days    | videoId   | Planned  |
| `heatmap-aggregated`        | 6          | 1 day     | videoId   | Planned  |
| `heatmap-alerts`            | 3          | 30 days   | videoId   | Planned  |

### `video.uploaded` — Active

```json
{
  "videoId": "uuid",
  "creatorId": "uuid",
  "filePath": "/media/uploads/uuid.mp4",
  "mimeType": "video/mp4",
  "title": "My Video Title",
  "uploadedAt": "2026-03-31T12:00:00Z"
}
```

Producer: Video Service → Consumers: Encoding Worker, Thumbnail Worker

### `video.processed` — Active

```json
{
  "videoId": "uuid",
  "creatorId": "uuid",
  "hlsPath": "/media/hls/uuid/index.m3u8",
  "thumbnailPath": "/media/thumbnails/uuid.jpg",
  "duration": 542.3,
  "processedAt": "2026-03-31T12:05:00Z"
}
```

Producer: Encoding Worker → Consumer: Summarization Service

### Planned Topics (brief)

**`viewer-interaction-events`** — Raw playback events (REWIND, PAUSE, SEEK, etc.) with `videoTs`, `sessionId`, `userId`.  
**`heatmap-aggregated`** — Aggregated segment counts per time window.  
**`heatmap-alerts`** — Viral segment alerts when metric exceeds 3σ above baseline.

---

## 4. MongoDB Collections — Planned

Two append-only collections with TTL indexes for automatic cleanup:

- **`processing_logs`** — Audit trail per encoding/thumbnail job. TTL: 30 days.
- **`error_logs`** — Centralized error collection across services. TTL: 7 days.

---

## 5. Data Lifecycle & Retention

| Store                    | Retention                   |
| ------------------------ | --------------------------- |
| `session:*` (Redis)      | 24h sliding TTL             |
| `stream:manifest:*`      | 5min TTL                    |
| `heatmap:*:live:*`       | 10min TTL (planned)         |
| `heatmap:*:total:*`      | 7 days, flushed hourly (planned) |
| `viewer_events` (PG)     | 90 days, partitions dropped (planned) |
| `processing_logs` (Mongo)| 30 days TTL (planned)       |
| `error_logs` (Mongo)     | 7 days TTL (planned)        |
| Kafka `video.*`          | 7 days                      |
| Kafka `viewer-*`         | 3 days (planned)            |
| Kafka `heatmap-alerts`   | 30 days (planned)           |

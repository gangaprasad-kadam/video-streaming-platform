# 🔥 Viewer Behavior Heatmap Engine

> **⚠️ STATUS: NOT YET IMPLEMENTED** — This is the planned unique feature for the project.

## Overview

Tracks viewer micro-interactions (pauses, rewinds, seeks, skips, speed changes) and aggregates them in real-time into an engagement heatmap overlaid on the video timeline. Creators see exactly which segments get replayed, skipped, or cause drop-offs — powered by an async event pipeline with zero impact on playback.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌──────────────────────────────────┐   ┌───────────────────────────────┐   │
│  │        Video Player (Viewer)     │   │   Creator Dashboard           │   │
│  │  On: pause / seek / rewind /     │   │  [====▓▓▓░░░▓▓▓▓░░░▓░░░====] │   │
│  │      skip / speed_change         │   │  Live heatmap overlay         │   │
│  │  → Fire lightweight event (async)│   │  (hot=▓, cold=░)              │   │
│  └─────────────┬────────────────────┘   └──────────────┬────────────────┘   │
│                │ HTTP POST (non-blocking)               │ SSE / WebSocket    │
└────────────────┼───────────────────────────────────────┼────────────────────┘
                 │                                        │
                 ▼                                        ▲
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY (NGINX)                                │
└────────────────┬────────────────────────────────────────┬───────────────────┘
                 │                                         │
                 ▼                                         ▼
┌────────────────────────────┐             ┌──────────────────────────────────┐
│  Event Ingestion Service   │             │       Heatmap API Service        │
│  • Validate JWT            │             │  • Read from Redis (live)        │
│  • Validate event schema   │             │  • Read from PostgreSQL (history)│
│  • Publish to Kafka        │             │  • Push SSE updates              │
│  • Return 202 Accepted     │             │  • REST endpoints for dashboard  │
└────────────┬───────────────┘             └──────────────────────────────────┘
             │                                            ▲
             ▼                                            │
┌────────────────────────────┐                           │
│   Kafka Topic:             │                           │
│  viewer-interaction-events │                           │
│  (partitioned by videoId)  │                           │
└────────────┬───────────────┘                           │
             │                                           │
             ▼                                           │
┌────────────────────────────────┐                      │
│  Heatmap Aggregation Service   │──── Write ──────────▶ Redis
│  • Kafka consumer group        │     (live window)
│  • Sliding 5-min window logic  │──── Flush ──────────▶ PostgreSQL
│  • Segment bucketing (per 5s)  │     (hourly snapshots)
│  • Anomaly detection (viral)   │
└────────────────────────────────┘
```

## Microservices

### 1. Event Ingestion Service (`/services/event-ingestion`)

Accepts raw viewer events, validates, and publishes to Kafka. Returns `202 Accepted` immediately.

```
POST /events/interaction
Authorization: Bearer <jwt>

Body:
{
  "videoId": "uuid",
  "eventType": "REWIND" | "PAUSE" | "SEEK" | "SKIP" | "SPEED_CHANGE" | "BUFFER",
  "timestamp": 142.5,        ← position in video (seconds)
  "seekFrom": 300.0,         ← only for SEEK events
  "clientTime": 1711882140,  ← unix timestamp for lag analysis
  "sessionId": "uuid"
}

Response: 202 Accepted
```

Events are batched client-side every 3 seconds before POST.

### 2. Heatmap Aggregation Service (`/services/heatmap-aggregator`)

Kafka consumer maintaining real-time segment counters in Redis, flushing hourly to PostgreSQL.

- **5-second buckets** — video timeline divided into segments
- **5-minute sliding window** in Redis for live heatmap
- **All-time cumulative counts** in Redis (evicted to PostgreSQL after 7 days)
- **Spike detection** — segment rewind rate >3σ above baseline → publishes to `heatmap-alerts` Kafka topic

### 3. Heatmap API Service (`/services/heatmap-api`)

Serves heatmap data to the creator dashboard via REST and SSE.

```
GET  /heatmap/:videoId                     → Full heatmap (all segments, all time)
GET  /heatmap/:videoId/live                → Live 5-min window heatmap
GET  /heatmap/:videoId/segment/:segmentId  → Detail for one segment
GET  /heatmap/:videoId/highlights          → Top 5 most-rewatched segments
SSE  /heatmap/:videoId/stream              → Real-time heatmap update stream
```

## Data Flow: Viewer Interaction (Happy Path)

```
Viewer Browser          Event Ingestion Svc     Kafka              Aggregation Svc     Redis
      │                         │                 │                       │               │
      │  [rewinds at t=142s]    │                 │                       │               │
      │── POST /events/interaction ──────────────▶│                       │               │
      │   { REWIND, ts:142 }    │                 │                       │               │
      │                         │── Validate JWT  │                       │               │
      │◀── 202 Accepted ────────│                 │                       │               │
      │   (instant, ~5ms)       │── Produce ──────▶                       │               │
      │                         │  viewer-interaction-events              │               │
      │                         │                 │── Consume ────────────▶               │
      │                         │                 │                       │── INCR ───────▶
      │                         │                 │                       │  heatmap:{vid}│
      │                         │                 │                       │  :seg:28:REWIND
      │                         │                 │                       │  (bucket 140-144s)
```

## Data Flow: Viral Segment Alert

```
Aggregation Svc  ──produce──▶  Kafka: heatmap-alerts  ──consume──▶  Notification Svc
                                                                           │
                                                                           └──▶ Creator Push Notif
                                                                               "Segment 2:20–2:25
                                                                                is going viral!
                                                                                67% rewatch rate"
```

## Data Models

### Redis Key Design

```
# Live heatmap (5-min sliding window, TTL: 10 min)
heatmap:{videoId}:live:{segmentId}    → Hash { REWIND: 45, PAUSE: 12, SEEK_TO: 8, SKIP: 3 }

# All-time cumulative (TTL: 7 days, flushed to Postgres)
heatmap:{videoId}:total:{segmentId}   → Hash { REWIND: 1203, PAUSE: 456, SEEK_TO: 89, SKIP: 34 }

# Video-level summary (TTL: 1 hour)
heatmap:{videoId}:summary             → Hash { totalEvents: 50000, hotSegment: 28, avgEngagement: 0.73 }

# Baseline stats for anomaly detection
heatmap:{videoId}:baseline:{segmentId} → Hash { mean: 12.4, stddev: 3.2 }
```

### PostgreSQL Schema

```sql
CREATE TABLE viewer_events (
    id            BIGSERIAL,
    video_id      UUID NOT NULL,
    user_id       UUID,
    session_id    UUID NOT NULL,
    event_type    VARCHAR(20) NOT NULL,
    video_ts      DECIMAL(10,3) NOT NULL,
    seek_from     DECIMAL(10,3),
    client_time   BIGINT NOT NULL,
    ingested_at   TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (ingested_at);

CREATE TABLE video_heatmap_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    video_id      UUID NOT NULL,
    segment_id    INTEGER NOT NULL,
    segment_start DECIMAL(10,3) NOT NULL,
    segment_end   DECIMAL(10,3) NOT NULL,
    rewind_count  INTEGER DEFAULT 0,
    pause_count   INTEGER DEFAULT 0,
    seek_to_count INTEGER DEFAULT 0,
    skip_count    INTEGER DEFAULT 0,
    total_viewers INTEGER DEFAULT 0,
    snapshot_hour TIMESTAMP NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW(),
    UNIQUE(video_id, segment_id, snapshot_hour)
);

CREATE TABLE viral_segment_alerts (
    id          BIGSERIAL PRIMARY KEY,
    video_id    UUID NOT NULL,
    segment_id  INTEGER NOT NULL,
    metric      VARCHAR(20),
    value       DECIMAL,
    baseline    DECIMAL,
    sigma       DECIMAL,
    alerted_at  TIMESTAMP DEFAULT NOW()
);
```

### Kafka Topics

| Topic | Partition Key | Partitions | Retention | Purpose |
|---|---|---|---|---|
| `viewer-interaction-events` | videoId | 12 | 3 days | Raw viewer events |
| `heatmap-aggregated` | videoId | 6 | 1 day | Aggregation → Heatmap API (SSE push) |
| `heatmap-alerts` | videoId | 3 | 7 days | Viral detection → Notification Svc |

## Sync vs Async Design

| Operation | Mode | Rationale |
|---|---|---|
| JWT validation | Sync | Must auth before accepting event |
| Publishing events to Kafka | Async | 202 returned immediately; fire-and-forget |
| Segment counter aggregation | Async | Kafka consumer, background processing |
| Hourly PostgreSQL flush | Async | Scheduled job, no user waits |
| Viral alert detection | Async | Push-based, non-blocking |
| Creator dashboard heatmap fetch | Sync | Blocking Redis read (sub-ms) |
| SSE push to dashboard | Async | Push-based, non-blocking |
| Client-side event batching | Async | Browser buffers 3s before POST |

## Edge Cases

| Scenario | Handling |
|---|---|
| Bot/scraper flood | Rate limit per sessionId (Redis token bucket, 100 events/min) |
| Repeated rewind on same segment | Deduplicate within 5s window by (sessionId, segmentId) |
| Ingestion service down | Client buffers in localStorage, retries on reconnect |
| Kafka consumer lag | Live heatmap shows last known state; alert if lag > 30s |
| No events yet | API returns empty heatmap `{}` |
| Anonymous viewers | Events accepted with userId=null, sessionId still tracked |
| Very short video (<30s) | Segment size reduced to 1s buckets |

## Integration Points

| Service | Source | Signal |
|---|---|---|
| Trending Service | Kafka: `viewer-interaction-events` | High REWIND rate → trending boost |
| Recommendation Svc | PostgreSQL: `video_heatmap_snapshots` | Recommend by engagement, not just views |
| Summarization Svc | Heatmap API (REST) | Auto-summarize top 3 hottest segments |
| Notification Svc | Kafka: `heatmap-alerts` | Viral segment push notifications |
| Video Service | Heatmap API (REST) | Embed highlight timestamps as chapter markers |

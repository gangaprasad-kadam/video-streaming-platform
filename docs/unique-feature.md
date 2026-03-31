# 🔥 Unique Feature: Viewer Behavior Heatmap Engine

## Overview

The **Viewer Behavior Heatmap Engine** tracks every micro-interaction a viewer makes while watching a video — pauses, rewinds, seeks, skips, speed changes — and aggregates them in real-time into a visual "engagement heatmap" overlaid on the video timeline.

This tells creators **exactly** which 30 seconds everyone replays, which parts everyone skips, and where viewers drop off — powered entirely by an async event pipeline, with zero impact on the viewer's playback experience.

---

## 🎯 Why This Feature Is Unique

Most platforms (YouTube, Netflix) have this data internally but never expose the architecture. Building it from scratch demonstrates a full real-time analytics pipeline covering every required concept.

| Aspect | Standard Analytics | Heatmap Engine |
|---|---|---|
| Granularity | View count, watch time | Per-second segment-level interaction data |
| Latency | Daily/hourly batch reports | Live updates (sub-5s lag) to creator dashboard |
| Impact on viewer | N/A | Zero — events are fire-and-forget via Kafka |
| Storage | Cold data warehouse | Hot (Redis) + Warm (PostgreSQL) tiered storage |
| Insight | "1M views" | "Segment 2:34–2:58 was rewatched by 67% of viewers" |

---

## 🏗️ High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│                                                                              │
│  ┌──────────────────────────────────┐   ┌───────────────────────────────┐   │
│  │        Video Player (Viewer)     │   │   Creator Dashboard           │   │
│  │                                  │   │                               │   │
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
│  (Fire-and-forget endpoint)│             │  (Serve heatmap to creators)     │
│                            │             │                                  │
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
│                                │     (live window)
│  • Kafka consumer group        │
│  • Sliding 5-min window logic  │──── Flush ──────────▶ PostgreSQL
│  • Segment bucketing (per 5s)  │     (hourly snapshots)
│  • Anomaly detection (viral)   │
└────────────────────────────────┘
```

---

## 🔧 New Microservices

### 1. Event Ingestion Service (`/services/event-ingestion`)

**Responsibility:** Accept raw viewer interaction events from the browser, validate them, and publish to Kafka. Must be extremely fast — returns `202 Accepted` immediately without waiting for processing.

**Endpoint:**
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

Response: 202 Accepted  (immediately, before Kafka publish completes)
```

**Why 202?** The browser fires this event and forgets. Waiting for a 200 would add latency to the viewer's interaction. The event is buffered client-side and batch-sent every 3 seconds.

---

### 2. Heatmap Aggregation Service (`/services/heatmap-aggregator`)

**Responsibility:** Kafka consumer that maintains real-time segment counters in Redis and periodically flushes aggregated snapshots to PostgreSQL.

**Key logic:**
- Divides video timeline into **5-second buckets** (segments)
- Maintains a **5-minute sliding window** in Redis for live heatmap
- Maintains **all-time cumulative counts** in Redis (evicted to PostgreSQL after 7 days)
- Detects "viral segments" — if a segment's rewind rate spikes >3σ, publishes to `heatmap-alerts` Kafka topic

---

### 3. Heatmap API Service (`/services/heatmap-api`)

**Responsibility:** Serve heatmap data to the creator dashboard via REST and real-time SSE (Server-Sent Events).

**Endpoints:**
```
GET  /heatmap/:videoId                     → Full heatmap (all segments, all time)
GET  /heatmap/:videoId/live                → Live 5-min window heatmap
GET  /heatmap/:videoId/segment/:segmentId  → Detail for one segment
GET  /heatmap/:videoId/highlights          → Top 5 most-rewatched segments
SSE  /heatmap/:videoId/stream              → Real-time heatmap update stream
```

---

## 🔄 Detailed Data Flows

### A. Viewer Watches & Interacts (Happy Path)

```
Viewer Browser          Event Ingestion Svc     Kafka              Aggregation Svc     Redis
      │                         │                 │                       │               │
      │  [watching video]       │                 │                       │               │
      │  [rewinds at t=142s]    │                 │                       │               │
      │                         │                 │                       │               │
      │── POST /events/interaction ──────────────▶│                       │               │
      │   { REWIND, ts:142 }    │                 │                       │               │
      │                         │── Validate JWT  │                       │               │
      │                         │── Validate schema                       │               │
      │◀── 202 Accepted ────────│                 │                       │               │
      │   (instant, ~5ms)       │── Produce ──────▶                       │               │
      │                         │  viewer-interaction-events              │               │
      │  [continues watching]   │                 │── Consume ────────────▶               │
      │                         │                 │   REWIND@t=142        │               │
      │                         │                 │                       │── INCR ───────▶
      │                         │                 │                       │  heatmap:{vid}│
      │                         │                 │                       │  :seg:28:REWIND
      │                         │                 │                       │  (bucket 140-144s)
```

### B. Creator Views Live Heatmap

```
Creator Browser         Heatmap API Svc          Redis              PostgreSQL
      │                       │                    │                     │
      │── GET /heatmap/:id ──▶│                    │                     │
      │                       │── GET heatmap:live ▶                     │
      │                       │◀── { seg0:2, seg1:45, seg28:312, ... }   │
      │◀── 200 Heatmap JSON ──│                    │                     │
      │                       │                    │                     │
      │── SSE /heatmap/:id/stream ────────────────▶│                     │
      │                       │── Subscribe ───────▶ (Redis Pub/Sub)     │
      │                       │                    │                     │
      │  [5s later]           │                    │                     │
      │                       │◀── PUBLISH heatmap-update                │
      │◀── SSE: data: {...} ──│  (triggered by aggregation svc)          │
      │  (heatmap updates     │                    │                     │
      │   in real time)       │                    │                     │
```

### C. Hourly Flush to PostgreSQL (Async Background Job)

```
Aggregation Svc           Redis                    PostgreSQL
      │                     │                           │
      │  [every 1 hour]     │                           │
      │── HGETALL heatmap:* ▶                           │
      │◀── all segment data─│                           │
      │── Compute stats ────│                           │
      │   (avg, p50, p95)   │                           │
      │── BULK INSERT ──────│──────────────────────────▶│
      │   video_heatmap_snapshots                       │
      │── EXPIRE old keys ──▶                           │
      │   (TTL: 7 days)     │                           │
```

### D. Viral Segment Alert Flow

```
Aggregation Svc     Kafka (heatmap-alerts)     Notification Svc     Creator
      │                      │                        │                 │
      │  [spike detected]    │                        │                 │
      │  seg:28 rewind rate  │                        │                 │
      │  > 3σ baseline       │                        │                 │
      │── Produce alert ─────▶                        │                 │
      │                      │── Consume ─────────────▶                 │
      │                      │                        │── Push notif ──▶│
      │                      │                        │  "Segment 2:20–2:25
      │                      │                        │   is going viral!
      │                      │                        │   67% rewatch rate"
```

---

## 🗄️ Data Models

### Redis Key Design

```
# Live heatmap (5-min sliding window, TTL: 10 min)
heatmap:{videoId}:live:{segmentId}
  → Hash { REWIND: 45, PAUSE: 12, SEEK_TO: 8, SKIP: 3 }

# All-time cumulative counts (TTL: 7 days, then flushed to Postgres)
heatmap:{videoId}:total:{segmentId}
  → Hash { REWIND: 1203, PAUSE: 456, SEEK_TO: 89, SKIP: 34 }

# Video-level summary (TTL: 1 hour, cache for dashboard)
heatmap:{videoId}:summary
  → Hash { totalEvents: 50000, hotSegment: 28, coldSegment: 72, avgEngagement: 0.73 }

# Baseline stats per segment (for anomaly detection)
heatmap:{videoId}:baseline:{segmentId}
  → Hash { mean: 12.4, stddev: 3.2 }
```

### PostgreSQL Schema

```sql
-- Raw event storage (partitioned by date)
CREATE TABLE viewer_events (
    id            BIGSERIAL,
    video_id      UUID NOT NULL,
    user_id       UUID,          -- nullable: anonymous viewers
    session_id    UUID NOT NULL,
    event_type    VARCHAR(20) NOT NULL,  -- REWIND, PAUSE, SEEK, SKIP, SPEED_CHANGE, BUFFER
    video_ts      DECIMAL(10,3) NOT NULL,  -- position in video (seconds)
    seek_from     DECIMAL(10,3),           -- for SEEK events only
    client_time   BIGINT NOT NULL,
    ingested_at   TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (ingested_at);

-- Hourly aggregated snapshots (long-term storage)
CREATE TABLE video_heatmap_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    video_id      UUID NOT NULL,
    segment_id    INTEGER NOT NULL,        -- 5-second bucket index
    segment_start DECIMAL(10,3) NOT NULL,  -- e.g., 140.0
    segment_end   DECIMAL(10,3) NOT NULL,  -- e.g., 145.0
    rewind_count  INTEGER DEFAULT 0,
    pause_count   INTEGER DEFAULT 0,
    seek_to_count INTEGER DEFAULT 0,
    skip_count    INTEGER DEFAULT 0,
    total_viewers INTEGER DEFAULT 0,       -- unique sessions
    snapshot_hour TIMESTAMP NOT NULL,      -- truncated to hour
    created_at    TIMESTAMP DEFAULT NOW(),
    UNIQUE(video_id, segment_id, snapshot_hour)
);

CREATE INDEX idx_heatmap_video_hour ON video_heatmap_snapshots(video_id, snapshot_hour DESC);
CREATE INDEX idx_heatmap_segment    ON video_heatmap_snapshots(video_id, segment_id);

-- Viral segment alerts log
CREATE TABLE viral_segment_alerts (
    id          BIGSERIAL PRIMARY KEY,
    video_id    UUID NOT NULL,
    segment_id  INTEGER NOT NULL,
    metric      VARCHAR(20),  -- e.g., REWIND_RATE
    value       DECIMAL,
    baseline    DECIMAL,
    sigma       DECIMAL,
    alerted_at  TIMESTAMP DEFAULT NOW()
);
```

### Kafka Topics

```
Topic: viewer-interaction-events
  Partition key : videoId   (ensures all events for a video go to same partition → ordered)
  Partitions    : 12        (scale by number of parallel aggregation consumers)
  Retention     : 3 days
  Payload:
  {
    "videoId":    "uuid",
    "userId":     "uuid | null",
    "sessionId":  "uuid",
    "eventType":  "REWIND | PAUSE | SEEK | SKIP | SPEED_CHANGE | BUFFER",
    "videoTs":    142.5,
    "seekFrom":   null,
    "clientTime": 1711882140,
    "ingestedAt": "ISO8601"
  }

Topic: heatmap-aggregated
  Partition key : videoId
  Partitions    : 6
  Retention     : 1 day
  Purpose       : Aggregation svc → Heatmap API svc (for SSE push)
  Payload:
  {
    "videoId":   "uuid",
    "segmentId": 28,
    "window":    "live | hourly",
    "counts":    { "REWIND": 45, "PAUSE": 12 },
    "updatedAt": "ISO8601"
  }

Topic: heatmap-alerts
  Partition key : videoId
  Partitions    : 3
  Retention     : 7 days
  Purpose       : Viral segment detection → Notification Service
  Payload:
  {
    "videoId":   "uuid",
    "creatorId": "uuid",
    "segmentId": 28,
    "metric":    "REWIND_RATE",
    "value":     0.67,
    "sigma":     4.2,
    "alertedAt": "ISO8601"
  }
```

---

## ⚙️ Async vs Sync Design Decisions

```
┌──────────────────────────────────────────────────────────────────────┐
│                     SYNCHRONOUS OPERATIONS                           │
│           (Must complete before responding — latency matters)        │
│                                                                      │
│  ✅ JWT validation in Event Ingestion Svc (must auth before accept)  │
│  ✅ GET /heatmap/:id — creator dashboard fetch (blocking read)       │
│  ✅ GET /heatmap/:id/highlights — top segments (blocking Redis read) │
│  ✅ Heatmap API reading from Redis (sub-ms, sync is fine here)       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                     ASYNCHRONOUS OPERATIONS                          │
│       (Fire-and-forget via Kafka — must not block viewer playback)   │
│                                                                      │
│  ✅ Publishing viewer events to Kafka (202 returned immediately)     │
│  ✅ Segment counter aggregation (Kafka consumer, background)         │
│  ✅ Hourly PostgreSQL flush (scheduled job, no user waits)           │
│  ✅ Viral alert detection & notification dispatch                    │
│  ✅ SSE push to creator dashboard (push-based, non-blocking)         │
│  ✅ Client-side event batching (browser buffers 3s before POST)      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Full Data Flow Diagram

```
                           VIEWER INTERACTION EVENT LIFECYCLE
                           ═══════════════════════════════════

  ┌─────────────┐
  │   Browser   │  pause/rewind/seek/skip
  │ (Viewer)    │──────────────────────────────────┐
  └─────────────┘  batched every 3s (async, client)│
                                                    ▼
                                       ┌────────────────────────┐
                                       │  Event Ingestion Svc   │
                                       │  POST /events/interact │
                                       │  → validate JWT        │
                                       │  → validate schema     │
                                       │  → 202 (immediate)     │
                                       └────────────┬───────────┘
                                                    │ produce
                                                    ▼
                                       ┌────────────────────────┐
                                       │  Kafka                 │
                                       │  viewer-interaction    │
                                       │  -events               │
                                       │  (partitioned:videoId) │
                                       └────────────┬───────────┘
                                                    │ consume
                                                    ▼
                                       ┌────────────────────────┐
                                       │  Heatmap Aggregation   │
                                       │  Service               │
                                       │                        │
                          ┌────────────┤  • bucket to 5s seg    ├────────────┐
                          │            │  • sliding window      │            │
                          │            │  • anomaly detect      │            │
                          ▼            └────────────┬───────────┘            ▼
               ┌──────────────────┐                │              ┌──────────────────┐
               │     Redis        │                │ (hourly)     │   PostgreSQL     │
               │                  │◀───── INCR ────┘              │                  │
               │  heatmap:{vid}   │                               │  video_heatmap   │
               │  :live:{seg}     │──── flush ───────────────────▶│  _snapshots      │
               │  heatmap:{vid}   │                               │                  │
               │  :total:{seg}    │                               │  viewer_events   │
               └────────┬─────────┘                               └──────────────────┘
                        │ pub/sub
                        ▼
               ┌──────────────────┐
               │  Heatmap API Svc │
               │                  │
               │  • REST reads    │──────────────▶  Creator Dashboard
               │  • SSE stream    │   (live heatmap overlay on video timeline)
               └──────────────────┘


                           VIRAL ALERT PATH
                           ════════════════

  Aggregation Svc  ──produce──▶  Kafka: heatmap-alerts
                                          │
                                          └──consume──▶  Notification Svc
                                                                 │
                                                                 └──▶  Creator Push Notif
```

---

## 🎨 Creator Dashboard UX (What They See)

```
  VIDEO ANALYTICS — "How I Built a Compiler from Scratch" (1h 24m)
  ┌─────────────────────────────────────────────────────────────────────┐
  │  Views: 128,493   Avg Watch Time: 47m   Rewatch Rate: 23%          │
  ├─────────────────────────────────────────────────────────────────────┤
  │                         ENGAGEMENT HEATMAP                         │
  │                                                                     │
  │  0:00    10:00    20:00   30:00   40:00   50:00   1:00:00  1:10:00 │
  │  ├────────────────────────────────────────────────────────────────┤ │
  │  │░░░░░▒▒▒▒▓▓▓▓▓▓████▓▓▒▒░░░░▓▓▓▓████████████▓▓▓▒▒░░░░░░▒▒▒▒▒▓▓│ │
  │  └────────────────────────────────────────────────────────────────┘ │
  │        ▲ intro skip        ▲ HOTTEST SEGMENT (67% rewatch)         │
  │                            └─ "The recursive descent parser demo"  │
  │                                                                     │
  │  💡 Insight: 2:34–2:58 has your highest rewatch rate.             │
  │     Consider making this a standalone short!                       │
  └─────────────────────────────────────────────────────────────────────┘

  Legend:  ░ low engagement  ▒ medium  ▓ high  █ very high (viral zone)
```

---

## 🔗 Integration with Existing Services

```
  Trending Service   ◄─── Kafka: viewer-interaction-events
  (High REWIND rate on a segment = signal for trending boost)

  Recommendation Svc ◄─── PostgreSQL: video_heatmap_snapshots
  (Recommend videos with high engagement scores, not just view counts)

  Summarization Svc  ◄─── Heatmap API (REST)
  (Auto-summarize the top 3 hottest segments instead of the whole video)

  Notification Svc   ◄─── Kafka: heatmap-alerts
  ("Your segment at 2:34 is going viral — 67% rewatch rate!")

  Video Service      ◄─── Heatmap API (REST, sync)
  (Embed highlight timestamps in video metadata for player chapter markers)
```

---

## 🔐 Edge Cases & Handling

| Scenario | Handling |
|---|---|
| Bot/scraper floods fake events | Rate limit per sessionId (Redis token bucket, 100 events/min) |
| Same user rewinding same segment in a loop | Deduplicate within 5s window by (sessionId, segmentId) |
| Event Ingestion Svc down | Client buffers events (localStorage), retries on reconnect |
| Kafka consumer lag (aggregation behind) | Live heatmap shows last known state; alert if lag > 30s |
| Video has no events yet | API returns empty heatmap `{}`, no error |
| Anonymous viewers (no JWT) | Events still accepted; userId = null, sessionId still tracked |
| Very short video (<30s) | Segment size reduced to 1s buckets instead of 5s |

---

## 📊 Scalability Numbers

```
Assumptions:
  • 10,000 concurrent viewers
  • Each viewer fires ~4 events/min (pause, seek, rewind, skip)
  • = 40,000 events/min = ~667 events/sec

Kafka:
  • 12 partitions on viewer-interaction-events
  • Each partition handles ~56 events/sec → well within limits

Redis:
  • 12 partitions × ~56 writes/sec = ~670 INCR ops/sec → trivial for Redis

Event Ingestion Service:
  • Stateless → horizontally scalable behind NGINX
  • Target: 2,000 req/sec per instance (Node.js non-blocking)

Aggregation Service:
  • 1 consumer group, 12 consumers (one per partition)
  • Scales by adding partitions + consumers
```

---

## ✅ Concept Coverage Matrix

| Concept | Where Used | Specific Implementation |
|---|---|---|
| **Async** | Event ingestion (202 immediately), client-side batching, PostgreSQL flush, SSE push, viral alerts | Kafka publish is non-blocking; viewer playback is never stalled |
| **Sync** | JWT validation, creator dashboard heatmap fetch, segment detail read | Redis reads are synchronous sub-ms operations |
| **Kafka** | `viewer-interaction-events` (ingestion), `heatmap-aggregated` (pipeline), `heatmap-alerts` (viral detection) | Partitioned by videoId for ordered, parallel processing |
| **Cache (Redis)** | Live 5-min sliding window counters, all-time totals, summary cache, rate limiting token buckets | Tiered: Redis for hot data, PostgreSQL for historical |
| **Microservices** | Event Ingestion Svc, Heatmap Aggregation Svc, Heatmap API Svc — each independently deployable and scalable | Loose coupling via Kafka; no direct service-to-service calls in hot path |

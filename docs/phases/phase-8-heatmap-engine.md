# Phase 8 — Viewer Behavior Heatmap Engine ⭐ (Unique Feature)

## Goal
The Heatmap Engine tracks every micro-interaction (pause, rewind, seek, skip) that viewers make while watching a video, aggregates them into per-second segment counts in real-time, and exposes this data to the creator dashboard as a live engagement heatmap.

This is the project's **unique feature**. See [`docs/unique-feature.md`](../unique-feature.md) for full architecture and design rationale.

---

## Three Components

| # | Service | Role | Port |
|---|---|---|---|
| 8a | `event-ingestion` | Accept viewer events, publish to Kafka (202 immediately) | 8006 |
| 8b | `heatmap-aggregator` | Kafka consumer → Redis segment counters + PostgreSQL flush | — |
| 8c | `heatmap-api` | REST + SSE — serve heatmap to creator dashboard | 8007 |

---

## 8a — Event Ingestion Service

### Folder Structure

```
services/event-ingestion/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py
    ├── config.py
    ├── database.py
    ├── redis_client.py
    ├── kafka_producer.py
    ├── exceptions.py        ← service-specific exceptions
    ├── logger.py            ← MongoDB ErrorLogger instance
    └── events/
        ├── router.py
        ├── service.py
        ├── cache.py         ← Redis rate-limit operations
        └── schemas.py
```

### Endpoint

```
POST /events/interaction
  Auth   : session cookie (get userId from session)
  Body:
  {
    "videoId":   "uuid",
    "eventType": "REWIND" | "PAUSE" | "SEEK" | "SKIP" | "SPEED_CHANGE" | "BUFFER",
    "videoTs":   142.5,      ← position in video (seconds)
    "seekFrom":  null,       ← only for SEEK
    "clientTime": 1711882140
  }
  Response: 202 Accepted    ← immediately, before Kafka publish completes
```

### Rate Limiting (Redis Token Bucket)

```python
async def check_rate_limit(session_id: str):
    key = f"ratelimit:events:{session_id}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 60)   # 1-minute window
    if current > 100:
        raise HTTPException(status_code=429, detail="Too many events")
```

### BackgroundTasks Pattern (LLD §7.6)

The endpoint returns `202 Accepted` immediately and delegates Kafka publish to FastAPI `BackgroundTasks` — the viewer's browser never waits for Kafka:

```python
# events/router.py
from fastapi import BackgroundTasks

@router.post("/events/interaction", status_code=202)
async def ingest_event(
    event: InteractionEvent,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    await check_rate_limit(user_id)
    background_tasks.add_task(kafka_producer.publish, event, user_id)
    return {"message": "accepted"}
```

### Watch History

> **Note:** Event Ingestion does **not** write to `watch_history`.
> The **Trending Service** (Phase 7) is the sole writer — it upserts `watch_history`
> when it consumes `PLAY` events from `viewer-interaction-events`.

### Kafka Publish

```python
# Publish after returning 202
await kafka_producer.send(
    "viewer-interaction-events",
    key=event.videoId.encode(),    # partition by videoId
    value={
        "videoId":    str(event.videoId),
        "userId":     user_id,
        "sessionId":  session_id,
        "eventType":  event.eventType,
        "videoTs":    event.videoTs,
        "seekFrom":   event.seekFrom,
        "clientTime": event.clientTime,
        "ingestedAt": datetime.utcnow().isoformat()
    }
)
```

---

## References Shared Patterns (8a)

This component follows all conventions in [`docs/phases/shared-patterns.md`](shared-patterns.md): layered architecture (§1, §8), standard `main.py` / `config.py` (§3, §4), `SuccessResponse` envelope (§5), `UNAUTHORIZED` / `RATE_LIMIT_EXCEEDED` error codes (§5), MongoDB error logger via `logger.py` (§7), Kafka partition key `key=videoId.encode()` (§6).

---

## 8b — Heatmap Aggregation Service

### Folder Structure

```
services/heatmap-aggregator/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py
    ├── config.py
    ├── database.py
    ├── redis_client.py
    ├── consumer.py         ← Kafka consumer loop
    ├── aggregator.py       ← segment bucketing + Redis writes
    ├── flusher.py          ← hourly PostgreSQL flush
    ├── viral_detector.py   ← anomaly detection
    ├── exceptions.py       ← service-specific exceptions
    ├── logger.py           ← MongoDB ErrorLogger instance
    └── heatmap/
        ├── repository.py   ← DB queries (viewer_events, snapshots)
        └── cache.py        ← Redis segment operations
```

### Segment Bucketing Logic

```python
# SEGMENT_SIZE comes from Settings — never hardcoded
# app/config.py
class Settings(BaseSettings):
    SEGMENT_SIZE: int = 5   # seconds per bucket
    ...

settings = Settings()

def get_segment_id(video_ts: float) -> int:
    return int(video_ts // settings.SEGMENT_SIZE)

# Example: videoTs=142.5 → segmentId=28  (bucket: 140s–145s)
```

### Redis Write Pattern

```python
async def record_event(event: dict):
    video_id   = event["videoId"]
    seg_id     = get_segment_id(event["videoTs"])
    event_type = event["eventType"]

    # Live 5-minute window counter (TTL: 10 min)
    live_key = f"heatmap:{video_id}:live:{seg_id}"
    await redis.hincrby(live_key, event_type, 1)
    await redis.expire(live_key, 600)

    # All-time cumulative counter (TTL: 7 days)
    total_key = f"heatmap:{video_id}:total:{seg_id}"
    await redis.hincrby(total_key, event_type, 1)
    await redis.expire(total_key, 604800)

    # Publish update to Redis pub/sub for SSE (Phase 8c)
    await redis.publish(
        f"heatmap-updates:{video_id}",
        json.dumps({"segId": seg_id, "eventType": event_type})
    )
```

### Viewer Events Table Write

The aggregator also writes each raw event to the `viewer_events` PostgreSQL table (partitioned by date) for long-term analytics and baseline recalculation:

```python
# consumer.py — inside consume loop, after Redis writes
await repo.insert_viewer_event(event)

# heatmap/repository.py
async def insert_viewer_event(event: dict):
    await db.execute(
        """
        INSERT INTO viewer_events
          (video_id, user_id, session_id, event_type, video_ts, seek_from, ingested_at)
        VALUES
          (:video_id, :user_id, :session_id, :event_type, :video_ts, :seek_from, :ingested_at)
        """,
        {
            "video_id":   event["videoId"],
            "user_id":    event["userId"],
            "session_id": event["sessionId"],
            "event_type": event["eventType"],
            "video_ts":   event["videoTs"],
            "seek_from":  event.get("seekFrom"),
            "ingested_at": event["ingestedAt"],
        }
    )
```

### Viral Segment Detection

```python
async def check_viral(video_id: str, seg_id: int):
    total_key = f"heatmap:{video_id}:total:{seg_id}"
    counts = await redis.hgetall(total_key)
    rewind_count = int(counts.get("REWIND", 0))

    baseline_key = f"heatmap:{video_id}:baseline:{seg_id}"
    baseline = await redis.hgetall(baseline_key)
    mean   = float(baseline.get("mean", 0))
    stddev = float(baseline.get("stddev", 1))

    if stddev > 0 and (rewind_count - mean) / stddev > 3.0:
        sigma = (rewind_count - mean) / stddev
        await kafka_producer.send("heatmap-alerts", key=video_id.encode(), value={
            "videoId":   video_id,
            "segmentId": seg_id,
            "metric":    "REWIND_RATE",
            "value":     rewind_count,
            "sigma":     sigma,
            "alertedAt": datetime.utcnow().isoformat()
        })
```

### Viral Segment Alert — DB Write

After publishing to Kafka, also insert into the `viral_segment_alerts` table for persistence and audit:

```python
# viral_detector.py — after kafka_producer.send(...)
    await repo.insert_viral_alert({
        "video_id":   video_id,
        "segment_id": seg_id,
        "metric":     "REWIND_RATE",
        "value":      rewind_count,
        "sigma":      sigma,
    })

# heatmap/repository.py
async def insert_viral_alert(alert: dict):
    await db.execute(
        """
        INSERT INTO viral_segment_alerts
          (video_id, segment_id, metric, value, sigma, alerted_at)
        VALUES
          (:video_id, :segment_id, :metric, :value, :sigma, NOW())
        """,
        alert
    )
```

### Baseline Recalculation

A weekly background task recomputes mean and standard deviation per segment from historical `viewer_events` PostgreSQL snapshots, then updates the Redis baseline keys used by `check_viral`:

```python
# flusher.py — weekly baseline task
async def weekly_baseline_recalc():
    while True:
        await asyncio.sleep(604800)   # 7 days
        rows = await repo.fetch_segment_stats()   # SELECT video_id, segment_id, AVG, STDDEV from viewer_events
        for row in rows:
            baseline_key = f"heatmap:{row['video_id']}:baseline:{row['segment_id']}"
            await redis.hset(baseline_key, mapping={
                "mean":   row["mean_rewind"],
                "stddev": row["stddev_rewind"],
            })
```

Started in `lifespan` alongside the hourly flush:

```python
asyncio.create_task(hourly_flush())
asyncio.create_task(weekly_baseline_recalc())
```

### Hourly PostgreSQL Flush

```python
# flusher.py — runs every hour via asyncio.sleep loop
async def hourly_flush():
    while True:
        await asyncio.sleep(3600)
        video_ids = await get_active_video_ids()   # Redis SCAN
        for video_id in video_ids:
            segments = await get_all_segments(video_id)
            await bulk_insert_snapshots(video_id, segments)
            # Reset live counters (keep total counters)
```

---

## References Shared Patterns (8b)

This component follows all conventions in [`docs/phases/shared-patterns.md`](shared-patterns.md): layered architecture with `repository.py` / `cache.py` under `heatmap/` (§1, §8), standard `main.py` / `config.py` templates (§3, §4), MongoDB error logger via `logger.py` (§7), idempotent Kafka consumer pattern (§10).

---

## 8c — Heatmap API Service

### Folder Structure

```
services/heatmap-api/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py
    ├── config.py
    ├── database.py
    ├── redis_client.py
    ├── consumer.py         ← Kafka consumer for heatmap-aggregated (SSE trigger)
    ├── exceptions.py       ← service-specific exceptions
    ├── logger.py           ← MongoDB ErrorLogger instance
    └── heatmap/
        ├── router.py
        ├── service.py
        ├── repository.py   ← DB queries (fallback reads from snapshots)
        └── cache.py        ← Redis segment reads + summary key
```

### Endpoints

```
GET /heatmap/:videoId
  Auth    : session cookie (must be video creator)
  Response: Full heatmap — all segments, all-time counts
  Source  : Redis total keys → fallback to PostgreSQL if expired
  {
    "videoId": "uuid",
    "segments": [
      { "segmentId": 28, "start": 140.0, "end": 145.0,
        "counts": { "REWIND": 312, "PAUSE": 45, "SEEK": 12, "SKIP": 3 },
        "totalInteractions": 372 }
    ],
    "hotSegment": { "segmentId": 28, "start": 140.0 },
    "coldSegment": { "segmentId": 72, "start": 360.0 }
  }
  Errors:
    401 UNAUTHORIZED — no session cookie / expired session
    403 FORBIDDEN    — authenticated but not the video creator

GET /heatmap/:videoId/live
  Response: Live 5-minute window heatmap (from Redis live keys)
  Updates every ~5s when client re-requests or via SSE
  Errors:
    401 UNAUTHORIZED
    403 FORBIDDEN

GET /heatmap/:videoId/highlights
  Response: Top 5 most-rewatched segments with labels
  {
    "highlights": [
      { "rank": 1, "segmentId": 28, "timestamp": 140.0,
        "rewindCount": 312, "label": "Segment 2:20–2:25" }
    ]
  }
  Errors:
    401 UNAUTHORIZED
    403 FORBIDDEN

SSE /heatmap/:videoId/stream
  Auth    : session cookie
  Protocol: text/event-stream
  Pushes  : real-time updates as viewers interact
  Source  : Redis pub/sub channel heatmap-updates:{videoId}
  Event format:
    data: {"segId": 28, "eventType": "REWIND", "newCount": 313}
```

### SSE Implementation

```python
@router.get("/{video_id}/stream")
async def stream_heatmap(video_id: str, request: Request):
    async def event_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"heatmap-updates:{video_id}")
        async for message in pubsub.listen():
            if await request.is_disconnected():
                break
            if message["type"] == "message":
                yield f"data: {message['data'].decode()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

### heatmap-aggregated Kafka Consumer (SSE Trigger)

The Heatmap API also subscribes to the `heatmap-aggregated` Kafka topic as an alternative/complement to Redis pub/sub for triggering SSE pushes. This decouples SSE delivery from direct Redis pub/sub availability:

```python
# consumer.py
async def consume_aggregated():
    consumer = AIOKafkaConsumer(
        "heatmap-aggregated",
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="heatmap-api-group",
        value_deserializer=lambda v: json.loads(v.decode())
    )
    await consumer.start()
    async for msg in consumer:
        event = msg.value
        # Re-publish to Redis pub/sub so SSE generators pick it up
        await redis.publish(
            f"heatmap-updates:{event['videoId']}",
            json.dumps({"segId": event["segmentId"], "eventType": event["eventType"]})
        )
```

Started in lifespan alongside the SSE server: `asyncio.create_task(consumer.consume_aggregated())`

### Summary Redis Key

On each `GET /heatmap/:videoId` request the service computes and caches a lightweight summary key for quick dashboard widgets:

```python
# heatmap/cache.py
SUMMARY_TTL = 300   # 5 minutes

async def update_summary(video_id: str, segments: list):
    total = sum(s["totalInteractions"] for s in segments)
    hot  = max(segments, key=lambda s: s["totalInteractions"])
    cold = min(segments, key=lambda s: s["totalInteractions"])
    await redis.hset(f"heatmap:{video_id}:summary", mapping={
        "hotSegment":        hot["segmentId"],
        "coldSegment":       cold["segmentId"],
        "totalInteractions": total,
    })
    await redis.expire(f"heatmap:{video_id}:summary", SUMMARY_TTL)
```

---

## References Shared Patterns (8c)

This component follows all conventions in [`docs/phases/shared-patterns.md`](shared-patterns.md): layered architecture with `repository.py` / `cache.py` under `heatmap/` (§1, §8), standard `main.py` / `config.py` templates (§3, §4), `SuccessResponse` envelope (§5), `UNAUTHORIZED` (401) and `FORBIDDEN` (403) error codes via `AuthError` / `ForbiddenError` (§5), MongoDB error logger via `logger.py` (§7).

---

## Tests (Phase 8)

```
tests/test_event_ingestion.py
  ✅ test_post_event_returns_202_immediately
  ✅ test_post_event_requires_auth
  ✅ test_rate_limit_exceeded_returns_429
  ✅ test_event_published_to_kafka

tests/test_heatmap_aggregator.py
  ✅ test_segment_bucketing_correct (ts=142.5 → seg=28)
  ✅ test_redis_incr_on_event
  ✅ test_viral_detection_publishes_alert
  ✅ test_hourly_flush_writes_to_postgres

tests/test_heatmap_api.py
  ✅ test_get_heatmap_returns_segments
  ✅ test_get_highlights_returns_top_5
  ✅ test_get_heatmap_unauthenticated_returns_401
  ✅ test_non_creator_returns_403
```

---

## Full Heatmap Data Flow

```
Viewer Browser
  │  POST /events/interaction { REWIND, ts:142.5 }
  │  ← 202 Accepted (3ms)
  ▼
Event Ingestion Service
  │  Kafka → viewer-interaction-events (key: videoId)
  ▼
Heatmap Aggregator (Kafka consumer)
  │  segId = int(142.5 // 5) = 28
  │  HINCRBY heatmap:{vid}:live:28  REWIND 1
  │  HINCRBY heatmap:{vid}:total:28 REWIND 1
  │  PUBLISH heatmap-updates:{vid} {segId:28, eventType:REWIND}
  ▼
Heatmap API SSE (Redis pub/sub subscriber)
  │  → SSE push to creator dashboard
  ▼
Creator Dashboard
  [====░░░░░░░████████████░░░░░░░] ← heatmap updates live
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| `POST /events/interaction` | Returns 202 async (fire & forget) | Must not delay viewer playback |
| Kafka publish (ingest) | Async background task | Non-blocking via aiokafka |
| Redis HINCRBY | Async (await) | Hot path — non-blocking critical |
| Redis PUBLISH (pub/sub) | Async (await) | Non-blocking |
| SSE streaming | Async generator | Push-based, never blocks |
| Hourly flush to PostgreSQL | Async loop | Background, no user waits |
| `GET /heatmap/:id` | Sync Redis read | Fast sub-ms, acceptable |
| Viral alert detection | Async | Background check after each event batch |

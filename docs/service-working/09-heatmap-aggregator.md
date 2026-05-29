# Heatmap Aggregator — Complete Technical Reference

## 1. What Is This Service?

The **heatmap-aggregator** is a **Kafka-consumer-only** service — it has no public HTTP endpoints
(only a health check). It listens continuously to `viewer-interaction-events`, maps each event to
a 5-second video segment (bucket), and writes weighted engagement scores to two stores:

1. **Redis DB 6** — Fast, dual-key per bucket: `total` (permanent) + `live` (5-minute TTL)
2. **MongoDB `heatmaps` DB** — Durable long-term storage of per-bucket engagement scores

The heatmap-api service reads from both of these stores independently, with no HTTP communication
between the two services.

**Port:** `8007` (internal Docker network: `heatmap-aggregator:8007`) — health check only  
**Cache:** Redis DB 6 (`redis://redis:6379/6`) — bucket counters  
**Database:** MongoDB (`heatmaps` DB, `heatmap_buckets` collection)  
**Kafka:** Consumes from `viewer-interaction-events` topic  
**Framework:** FastAPI (health only) + aiokafka + motor (async MongoDB driver)

---

## 2. Folder Structure

```
heatmap-aggregator/
├── app/
│   ├── main.py                ← FastAPI app, lifespan: connect Redis+Mongo, start consumer task
│   ├── config.py              ← Pydantic-Settings (REDIS_URL, KAFKA_*, MONGO_*, BUCKET_SIZE, LIVE_TTL)
│   ├── redis_client.py        ← Singleton Redis connection + get_redis()
│   ├── mongo_client.py        ← Motor singleton + get_db()
│   │
│   └── heatmap/               ← Heatmap domain
│       ├── handler/
│       │   └── consumer.py    ← Kafka consumer loop (runs as asyncio task)
│       ├── utils/
│       │   ├── service.py     ← Business logic: weight lookup → Redis write → MongoDB upsert
│       │   ├── schemas.py     ← InteractionEvent + ACTION_WEIGHTS dict
│       │   └── cache.py       ← Redis dual-write logic (_bucket(), record_event())
│       └── dao/
│           └── repository.py  ← MongoDB upsert_bucket() query
│
├── tests/
│   └── test_heatmap_aggregator.py ← 7 tests: bucket math, Redis keys, Mongo upsert, health
├── Dockerfile
├── requirements.txt           ← motor==3.7.1 (required for pymongo 4.x compatibility)
└── pytest.ini
```

---

## 3. Three-Layer Architecture

```
Kafka Message
    │
    ▼
handler/consumer.py     ← Decodes JSON, builds InteractionEvent, calls service
    │                      Never touches Redis or MongoDB directly
    ▼
utils/service.py        ← Looks up ACTION_WEIGHTS, coordinates Redis + MongoDB writes
    │
    ├──► utils/cache.py     ← Redis dual-write (total + live keys via pipeline)
    └──► dao/repository.py  ← MongoDB upsert_bucket()
```

**Layer rules:**
- `consumer.py` → calls `utils/service.py` only
- `utils/service.py` → calls `utils/cache.py` + `dao/repository.py`
- `dao/repository.py` → raw Motor (MongoDB) queries only

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/6` | Redis DB 6 (shared with heatmap-api) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker |
| `KAFKA_TOPIC_CONSUME` | `viewer-interaction-events` | Topic to consume from |
| `KAFKA_GROUP_ID` | `heatmap-aggregator` | Consumer group for offset tracking |
| `MONGO_URL` | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGO_DB` | `heatmaps` | Database name (shared with heatmap-api) |
| `BUCKET_SIZE` | `5` | Width of each heatmap bucket in seconds |
| `LIVE_TTL` | `300` | TTL for live Redis keys in seconds (5 minutes) |

---

## 5. Entry Point (main.py)

The lifespan hook connects to Redis and MongoDB, then starts the Kafka consumer as an asyncio task:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_redis()
    await connect_mongo()
    consumer_task = asyncio.create_task(run_consumer())
    yield
    consumer_task.cancel()
    await asyncio.gather(consumer_task, return_exceptions=True)
    await close_mongo()
    await close_redis()
```

**No HTTP router is included** — only the health endpoint on `app` directly. All work happens
inside the `run_consumer()` asyncio task that runs in the background.

---

## 6. Kafka Consumer (handler/consumer.py)

```python
consumer = AIOKafkaConsumer(
    settings.KAFKA_TOPIC_CONSUME,          # "viewer-interaction-events"
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    group_id=settings.KAFKA_GROUP_ID,      # "heatmap-aggregator"
    auto_offset_reset="latest",            # Only events after this service starts
    enable_auto_commit=True,
)
```

**Processing loop:**
```python
async for msg in consumer:
    payload = json.loads(msg.value.decode("utf-8"))
    event = InteractionEvent(**payload)
    redis = get_redis()
    db = get_db()
    await heatmap_service.handle_interaction(db, redis, event)
```

Each message is fully processed (Redis + MongoDB) before the next message is consumed.
Errors in individual messages are caught and logged — they do not crash the consumer loop.

**`auto_offset_reset="latest"` vs `"earliest"`:**
- `"latest"` — Only events arriving after this service starts are processed. Historical events
  are not replayed. This is correct for real-time heatmaps — old events would inflate scores
  for videos that may no longer be relevant.

---

## 7. Bucketing Algorithm (utils/cache.py)

The core of the heatmap engine: mapping a floating-point video timestamp to a discrete 5-second bucket.

```python
BUCKET_SIZE = 5  # seconds

def _bucket(video_ts: float) -> int:
    """Map a video timestamp (seconds) to the start of its 5-second bucket."""
    return int(video_ts // BUCKET_SIZE) * BUCKET_SIZE
```

**Examples:**

| `videoTs` | Bucket | Label |
|---|---|---|
| `0.0` | `0` | `0:00–0:05` |
| `4.9` | `0` | `0:00–0:05` |
| `5.0` | `5` | `0:05–0:10` |
| `7.9` | `5` | `0:05–0:10` |
| `142.5` | `140` | `2:20–2:25` |
| `144.9` | `140` | `2:20–2:25` |
| `145.0` | `145` | `2:25–2:30` |

This bucketing means a viewer who rewinds between seconds 140 and 145 multiple times will
accumulate score on bucket 140 — making that segment visible as a "hot spot" in the heatmap.

---

## 8. Action Weights (utils/schemas.py)

```python
ACTION_WEIGHTS: dict[str, int] = {
    "REWIND":         3,   # strongest re-engagement signal
    "WATCH_COMPLETE": 2,   # user watched to the end
    "SEEK":           2,   # intentional navigation to this segment
    "PAUSE":          1,   # mild interest
    "PLAY":           1,   # basic play
    "SKIP":          -1,   # disengagement signal
}
```

**Rationale:**
- `REWIND` is weighted highest because re-watching a segment is the clearest signal of interest.
- `WATCH_COMPLETE` signals the video (and likely this segment) held the viewer's attention.
- `SEEK` shows intentional navigation — the viewer wanted to reach this specific point.
- `SKIP` is negative — it signals the viewer actively avoided this segment.
- Unknown actions are skipped entirely with a warning log.

---

## 9. Redis Dual-Write (utils/cache.py)

Each event writes to **two Redis keys per bucket** in a single pipeline:

```python
async def record_event(redis: Redis, event: InteractionEvent) -> int:
    bucket = _bucket(event.videoTs)
    weight = ACTION_WEIGHTS.get(event.action, 1)

    total_key = f"heatmap:{event.videoId}:total:{bucket}"
    live_key  = f"heatmap:{event.videoId}:live:{bucket}"

    async with redis.pipeline(transaction=False) as pipe:
        pipe.incrby(total_key, weight)      # permanent, no TTL
        pipe.incrby(live_key, weight)       # expires in LIVE_TTL seconds
        pipe.expire(live_key, settings.LIVE_TTL)
        await pipe.execute()

    return bucket
```

**Key patterns:**

| Key | TTL | Purpose |
|---|---|---|
| `heatmap:{videoId}:total:{bucket}` | None (permanent) | All-time cumulative score |
| `heatmap:{videoId}:live:{bucket}` | 300s (5 min) | Recent activity window |

**Why two keys?**
- `total` powers the historical heatmap — shows the all-time most-replayed segments.
- `live` powers the real-time heatmap — shows what segments are hot **right now**. After 5
  minutes of no activity on a bucket, the live key expires automatically.

**Why a pipeline?**  
The `INCRBY` + `EXPIRE` for the live key must be atomic — if the service crashes between them,
the live key would have no TTL and accumulate forever. The pipeline batches all 3 operations in a
single round-trip, minimising the window for partial writes.

---

## 10. MongoDB Schema (dao/repository.py)

**Collection:** `heatmap_buckets` in the `heatmaps` database

**Document structure:**
```json
{
  "videoId":      "550e8400-e29b-41d4-a716-446655440002",
  "bucket":       140,
  "score":        47,
  "last_updated": "2024-01-15T10:30:00.000000+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| `videoId` | string | UUID of the video |
| `bucket` | int | Start second of the 5-second window (e.g. 140 = seconds 140–144) |
| `score` | int | Cumulative weighted engagement score |
| `last_updated` | ISO 8601 string | Timestamp of the last write |

**Upsert operation:**
```python
await db.heatmap_buckets.update_one(
    {"videoId": video_id, "bucket": bucket},   # filter: unique per (video, bucket)
    {
        "$inc":         {"score": weight},     # increment score atomically
        "$set":         {"last_updated": now},
        "$setOnInsert": {"videoId": video_id, "bucket": bucket},
    },
    upsert=True,
)
```

**`$setOnInsert`** only runs on the first insert (when the document doesn't exist yet). This avoids
overwriting `videoId` and `bucket` on every update, keeping the operation efficient.

**Why MongoDB and not PostgreSQL?**
- Heatmap data is schema-less by nature — video length varies, number of buckets varies.
- MongoDB's `$inc` upsert in a single command is exactly the right primitive for counters.
- The heatmap-api needs flexible queries (all buckets, top-N buckets) without JOINs.

---

## 11. Business Logic (utils/service.py)

```python
async def handle_interaction(db, redis, event: InteractionEvent) -> None:
    if event.action not in ACTION_WEIGHTS:
        logger.warning("Unknown action '%s' — skipping", event.action)
        return

    weight = ACTION_WEIGHTS[event.action]
    bucket = await record_event(redis, event)       # Redis write
    await repo.upsert_bucket(db, event.videoId, bucket, weight)  # MongoDB write

    logger.info("Recorded %s (w=%d) for video=%s bucket=%ds",
                event.action, weight, event.videoId, bucket)
```

**Order of operations:**
1. Validate action is known — skip silently with warning if not.
2. Write to Redis first (fast, in-memory, sub-ms).
3. Write to MongoDB second (durable, slower).

If MongoDB write fails, Redis already has the score — the live heatmap still works. The MongoDB
failure will be retried on the next delivery of the same event (if Kafka redelivers it).

---

## 12. Testing

**Test runner:** `pytest` with `pytest-asyncio`

**Test strategy:**
- **Redis:** `AsyncMock` with a mock pipeline (`__aenter__`/`__aexit__` setup)
- **MongoDB:** `AsyncMock` for `db.heatmap_buckets.update_one`
- **No real Kafka** — consumer is not tested via HTTP; service functions are tested directly

**Run tests:**
```bash
cd backend/heatmap-aggregator
python -m pytest tests/ -v
# Expected: 7 passed
```

**Test coverage:**

| Test | What it covers |
|---|---|
| `test_bucket_exact` | `_bucket(0.0)=0`, `_bucket(5.0)=5`, `_bucket(10.0)=10` |
| `test_bucket_rounds_down` | `_bucket(7.9)=5`, `_bucket(142.5)=140`, `_bucket(145.0)=145` |
| `test_record_event_increments_correct_bucket` | REWIND at 142.5s → `incrby total:140 3` + `incrby live:140 3` |
| `test_record_event_skip_negative_weight` | SKIP at 30s → `incrby total:30 -1` |
| `test_handle_interaction_unknown_action_skipped` | Unknown action → `upsert_bucket` NOT called |
| `test_handle_interaction_upserts_mongo` | PAUSE at 60s → `upsert_bucket(db, "vid-1", 60, 1)` |
| `test_health` | `GET /health` → `{"status": "ok"}` |

---

## 13. How It Fits in the Full Pipeline

```
[event-ingestion service]
POST /events/interaction → Kafka publish
        │
        ▼
[Kafka topic: viewer-interaction-events]
        │
        ├────────────────────────────────┐
        ▼                               ▼
[trending-service consumer]    [heatmap-aggregator consumer]  ← THIS SERVICE
  Redis DB 4 sorted set           Redis DB 6 bucket counters
  PostgreSQL watch_history        MongoDB heatmap_buckets

                                         │
        ┌────────────────────────────────┘
        │
        ▼
[heatmap-api service]
  GET /heatmap/{id}          → reads MongoDB heatmap_buckets
  GET /heatmap/{id}/live     → reads Redis DB 6 live:* keys
  GET /heatmap/{id}/highlights → reads MongoDB, sorted by score desc
```

---

## 14. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework (health check only) |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `redis[asyncio]` | 5.0.3 | Async Redis client |
| `aiokafka` | 0.10.0 | Async Kafka consumer |
| `motor` | 3.7.1 | Async MongoDB driver (Motor) |
| `pydantic[email]` | 2.6.4 | Event schema validation |
| `pydantic-settings` | 2.2.1 | Config from environment |

> **Important:** `motor==3.7.1` is required. Earlier versions (e.g. 3.3.2) are incompatible with
> pymongo 4.x and will raise `ImportError: cannot import name '_QUERY_OPTIONS'` at startup.

---

## 15. Data Flow Diagram

```
KAFKA                  HEATMAP-AGGREGATOR              REDIS(DB6)         MONGODB
  │                          │                             │                  │
  │── viewer-interaction ───►│                             │                  │
  │    event JSON             │                             │                  │
  │                          │── _bucket(videoTs=142.5) → bucket=140          │
  │                          │── ACTION_WEIGHTS["REWIND"] → weight=3          │
  │                          │── redis.pipeline()                             │
  │                          │       incrby total:140  3 ─────────────────────►│
  │                          │       incrby live:140   3 ─────────────────────►│
  │                          │       expire  live:140  300s ──────────────────►│
  │                          │── upsert_bucket("vid", 140, 3) ────────────────►│
  │                          │       $inc score: 3                             │
  │                          │       $set last_updated: now                   │
```

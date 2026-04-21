# Trending Service — Complete Technical Reference

## 1. What Is This Service?

The **trending-service** is a FastAPI microservice that maintains a real-time video leaderboard
and serves personalised recommendations. It combines two running components inside one process:

1. **HTTP Server** — Two public REST endpoints (`/trending`, `/trending/recommendations/{userId}`)
2. **Kafka Consumer** — Listens to `viewer-interaction-events` and scores videos in Redis
3. **Score Decay Loop** — Background asyncio task that depreciates scores by 10% every hour

Unlike the encoding/thumbnail workers, this service runs as a **full FastAPI app** with HTTP
endpoints, a Kafka consumer, and a scheduled background task all co-existing in the same process
via asyncio tasks.

**Port:** `8005` (internal Docker network: `trending-service:8005`)  
**Database:** PostgreSQL (`videoplatform`) — `watch_history` table; read-only access to `videos`  
**Cache:** Redis DB 4 (`redis://redis:6379/4`) — sorted set for trending scores  
**Kafka:** Consumes from `viewer-interaction-events` topic  
**Framework:** FastAPI + SQLAlchemy (async) + asyncpg + aiokafka

---

## 2. Folder Structure

```
trending-service/
├── app/
│   ├── main.py               ← FastAPI app, lifespan hooks, starts consumer + decay tasks
│   ├── config.py             ← Pydantic-Settings (TRENDING_KEY, SCORE_DECAY_FACTOR, etc.)
│   ├── database.py           ← SQLAlchemy async engine + get_db()
│   ├── redis_client.py       ← Singleton Redis connection + get_redis()
│   ├── models.py             ← WatchHistory ORM model + read-only Video mirror
│   ├── exceptions.py         ← Service-specific exceptions
│   │
│   └── trending/             ← Trending domain
│       ├── handler/
│       │   ├── router.py     ← HTTP routes (GET /trending, GET /recommendations)
│       │   ├── consumer.py   ← Kafka consumer loop for viewer-interaction-events
│       │   └── decay.py      ← Hourly score decay background task
│       ├── utils/
│       │   ├── service.py    ← Business logic (handle_interaction, get_trending, get_recommendations)
│       │   ├── cache.py      ← Redis sorted set ops (ZINCRBY, ZREVRANGE, apply_score_decay)
│       │   └── schemas.py    ← Pydantic request/response models
│       └── dao/
│           └── repository.py ← DB queries (watch_history, videos by IDs/creators)
│
├── migrations/
│   ├── env.py
│   └── versions/
│       └── 001_create_watch_history.py
├── tests/
│   ├── conftest.py           ← fixtures: SQLite in-memory, AsyncMock Redis
│   └── test_trending.py      ← 7 tests covering all endpoints
├── Dockerfile
├── alembic.ini
├── requirements.txt
└── pytest.ini
```

---

## 3. Three-Layer Architecture

```
HTTP Request                Kafka Message              Background Loop
      │                           │                           │
      ▼                           ▼                           ▼
handler/router.py         handler/consumer.py         handler/decay.py
      │                           │                           │
      └───────────────────────────┘                           │
                      ▼                                       ▼
              utils/service.py          ←────────── utils/cache.py (ZINCRBY decay)
                      │
              ┌───────┴──────────┐
              ▼                  ▼
      utils/cache.py      dao/repository.py
      (Redis sorted set)  (PostgreSQL queries)
```

**Layer rules:**
- `handler/router.py` → calls `utils/service.py` only
- `handler/consumer.py` → calls `utils/service.py` only
- `handler/decay.py` → calls `utils/cache.py` directly (no DB needed for decay)
- `utils/service.py` → calls `dao/repository.py` + `utils/cache.py`
- `dao/repository.py` → raw SQLAlchemy queries only

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/4` | Redis DB 4 for trending scores |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker |
| `KAFKA_GROUP_ID` | `trending-service` | Consumer group (enables offset tracking) |
| `KAFKA_TOPIC_CONSUME` | `viewer-interaction-events` | Topic to listen on |
| `TRENDING_KEY` | `trending:scores` | Redis sorted set key |
| `TRENDING_LIMIT` | `20` | Default number of trending results |
| `SCORE_DECAY_FACTOR` | `0.9` | Hourly score multiplier (10% decay) |

---

## 5. Entry Point (main.py)

The lifespan hook starts two asyncio background tasks alongside the HTTP server:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await connect_redis()

    consumer_task = asyncio.create_task(run_consumer())   # Kafka consumer
    decay_task = asyncio.create_task(run_decay_loop())    # Hourly score decay

    yield  # HTTP server runs here

    consumer_task.cancel()
    decay_task.cancel()
    await asyncio.gather(consumer_task, decay_task, return_exceptions=True)
    await close_redis()
    await close_db()
```

**Why asyncio tasks (not threads)?**  
The Kafka consumer and decay loop are `async` — they `await` I/O (network, Redis) and never block
the event loop. asyncio tasks run concurrently within the same thread, so uvicorn's HTTP server
handles requests while the consumer waits for Kafka messages.

---

## 6. Kafka Consumer (handler/consumer.py)

### Consumer Setup

```python
consumer = AIOKafkaConsumer(
    settings.KAFKA_TOPIC_CONSUME,          # "viewer-interaction-events"
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    group_id=settings.KAFKA_GROUP_ID,      # "trending-service"
    auto_offset_reset="latest",            # Only new events (skip old backlog)
    enable_auto_commit=True,
)
```

**`auto_offset_reset="latest"` vs `"earliest"`:**
- `"latest"` — Only process events that arrive *after* this service starts. Historical events
  are not replayed. This is correct for real-time trending (stale old events shouldn't inflate
  scores).
- Contrast with encoding-worker which uses `"earliest"` — it must process every upload even
  if it restarted mid-pipeline.

### Event Processing

```python
async for msg in consumer:
    payload = json.loads(msg.value.decode("utf-8"))
    event = InteractionEvent(**payload)
    redis = get_redis()
    async with AsyncSessionFactory() as db:
        await trending_service.handle_interaction(db, redis, event)
```

Each message dispatches to `handle_interaction` which:
1. Calls `cache.increment_score(redis, videoId, action)` → `ZINCRBY trending:scores {delta} {videoId}`
2. On `PLAY` events with a `creatorId`: upserts `watch_history` in PostgreSQL

---

## 7. Interaction Event Schema

Events published to `viewer-interaction-events` (by event-ingestion service in Phase 8):

```json
{
  "userId":    "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "videoId":   "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
  "action":    "PLAY",
  "videoTs":   45.2,
  "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "sessionId": "sess-abc-123",
  "timestamp": "2024-01-15T10:00:00"
}
```

| Field | Description |
|---|---|
| `userId` | Who performed the action |
| `videoId` | Which video |
| `action` | `PLAY`, `WATCH_COMPLETE`, `REWIND`, `SEEK`, `PAUSE`, `SKIP` |
| `videoTs` | Timestamp in video (seconds) at which action occurred |
| `creatorId` | Creator of the video (needed for watch history + recommendations) |
| `sessionId` | Browser session (for deduplication in future phases) |
| `timestamp` | ISO 8601 wall-clock time |

### Score Weights

| Action | Delta | Rationale |
|---|---|---|
| `PLAY` | +1.0 | Basic engagement signal |
| `WATCH_COMPLETE` | +10.0 | Strong signal — user watched to the end |
| `REWIND` | +3.0 | User re-watched a segment — high interest |
| `SEEK` | +1.0 | User navigated to a specific point |
| `PAUSE` | +0.5 | Light engagement |
| `SKIP` | -0.5 | Negative signal — user skipped |

---

## 8. Redis Sorted Set (utils/cache.py)

The trending leaderboard is a **Redis sorted set** — a data structure where each member
(video ID) has an associated floating-point score. Redis maintains them sorted by score.

### Key operations

```python
# Add/increment score when viewer interacts
ZINCRBY trending:scores {delta} {videoId}
# e.g. ZINCRBY trending:scores 10.0 "eeee-eeee-..."

# Fetch top N by score (descending)
ZREVRANGE trending:scores 0 {N-1} WITHSCORES
# Returns: [("eeee-...", 150.5), ("aaaa-...", 87.0), ...]

# Decay: multiply all scores by 0.9, remove entries below 0.01
# (done in a pipeline for atomicity)
ZRANGE trending:scores 0 -1 WITHSCORES  → for each: ZADD or ZREM
```

### Why Redis sorted sets?

- `ZINCRBY` is O(log N) — extremely fast even with millions of entries
- `ZREVRANGE` is O(log N + M) — fetches top M results in sub-millisecond time
- The sorted set automatically maintains order — no sorting needed in application code
- TTL-less — scores persist until explicitly removed (decay loop handles cleanup)

---

## 9. Score Decay Algorithm (handler/decay.py)

Every hour, the decay loop:
1. Fetches ALL members + scores from `trending:scores` via `ZRANGE ... WITHSCORES`
2. Multiplies each score by `SCORE_DECAY_FACTOR` (0.9)
3. If new score < 0.01 → removes the entry (`ZREM`)
4. Otherwise → updates with `ZADD trending:scores {newScore} {videoId}`
5. All operations run in a **Redis pipeline** (batched, single round-trip)

```python
async def apply_score_decay(redis: Redis) -> int:
    members = await redis.zrange(settings.TRENDING_KEY, 0, -1, withscores=True)
    pipe = redis.pipeline()
    removed = 0
    for video_id, score in members:
        new_score = score * settings.SCORE_DECAY_FACTOR
        if new_score < 0.01:
            pipe.zrem(settings.TRENDING_KEY, video_id)
            removed += 1
        else:
            pipe.zadd(settings.TRENDING_KEY, {video_id: new_score})
    await pipe.execute()
    return removed
```

**Effect over time:**
```
After 1h:  score × 0.9
After 2h:  score × 0.81
After 24h: score × 0.08   (viral spike cools down in ~12h)
After 48h: score × 0.006  (effectively gone)
```

This ensures yesterday's viral video doesn't dominate forever — fresh content can overtake it.

---

## 10. HTTP Endpoints

### GET /trending

Returns the top N videos from the Redis sorted set, enriched with metadata from PostgreSQL.

```
GET /trending?limit=20
```

**Flow:**
1. `ZREVRANGE trending:scores 0 {limit-1} WITHSCORES` → list of (videoId, score)
2. `SELECT * FROM videos WHERE id IN (...) AND status = 'ready'` → metadata
3. Inner join: skip videoIds not in DB (deleted videos or encoding failures)
4. Build ranked list (rank 1 = highest score)

**Response:**
```json
{
  "data": {
    "videos": [
      {
        "video_id": "eeee-...",
        "title": "My Video",
        "creator_id": "cccc-...",
        "thumbnail_path": "/media/thumbnails/eeee-....jpg",
        "duration": 45.2,
        "score": 150.5,
        "rank": 1
      }
    ],
    "total": 1
  }
}
```

**Query params:**
- `limit` (int, 1–100, default 20) — how many results to return

---

### GET /trending/recommendations/{userId}

Hybrid personalised recommendations: **60% trending + 40% creator-based**, minus already watched.

```
GET /trending/recommendations/{userId}?limit=20
```

**Algorithm:**
```
1. Get top 50 trending videoIds from Redis (oversample to have enough after filtering)
2. Get user's watch history from watch_history table
3. Remove watched videoIds from trending candidates
4. Extract distinct creatorIds from watch history
5. Query videos from those creators, excluding all watched + trending picks
6. Merge:
   trending_slots = ceil(limit × 0.6)  ← e.g. 12 slots for limit=20
   creator_slots  = limit - trending_slots  ← e.g. 8 slots
7. Each item tagged with reason="trending" or reason="creator"
```

**Response:**
```json
{
  "data": {
    "user_id": "ffff-...",
    "videos": [
      {
        "video_id": "eeee-...",
        "title": "Trending Video",
        "creator_id": "cccc-...",
        "thumbnail_path": "...",
        "duration": 45.2,
        "reason": "trending"
      },
      {
        "video_id": "dddd-...",
        "title": "Creator Video",
        "creator_id": "cccc-...",
        "thumbnail_path": "...",
        "duration": 30.0,
        "reason": "creator"
      }
    ],
    "total": 2
  }
}
```

---

## 11. Database Schema

### watch_history table

Created by Alembic migration `001_create_watch_history.py`.

```sql
CREATE TABLE watch_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    video_id    UUID NOT NULL,
    creator_id  UUID NOT NULL,       -- denormalised for fast creator-based queries
    watched_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, video_id)       -- upsert idempotency
);

CREATE INDEX ON watch_history (user_id);
CREATE INDEX ON watch_history (video_id);
```

**Why denormalise `creator_id`?**  
To build creator-based recommendations, we need the creator of each watched video.
Without denormalisation, we'd need a `JOIN` to the `videos` table. Since `creator_id` is
immutable (a video's creator never changes), denormalising it here is safe and avoids the join.

**Upsert behaviour:**  
`ON CONFLICT (user_id, video_id) DO NOTHING` — re-playing a video doesn't create duplicate
rows. The `UNIQUE` constraint ensures idempotency even if the same Kafka event is redelivered.

---

## 12. How the Watch History Gets Populated

Watch history is populated **only on `PLAY` events** with a `creatorId` field:

```python
async def handle_interaction(db, redis, event):
    await increment_score(redis, event.videoId, event.action)

    if event.action == "PLAY" and event.creatorId:
        await repo.upsert_watch_history(db, event.userId, event.videoId, event.creatorId)
```

**Why only on PLAY?**
- `PLAY` means the user intentionally started watching — strong interest signal
- `SEEK`, `PAUSE`, `REWIND` might happen from a video the user is already watching — no new
  information about their preferences
- Recording only `PLAY` keeps watch_history lean and prevents double-counting

---

## 13. Testing Pattern

```
pytest tests/ -v
```

- **DB:** SQLite in-memory (`aiosqlite`) — `WatchHistory` and `Video` tables
- **Redis:** `AsyncMock` — `zrevrange`, `zincrby`, `zrange` mocked
- **HTTP:** `httpx.AsyncClient` with `ASGITransport`
- **Overrides:** `app.dependency_overrides[get_db]` + `app.dependency_overrides[get_redis]`

```bash
cd services/trending-service && python3 -m pytest tests/ -v
```

**7 tests:**

| Test | What it covers |
|---|---|
| `test_health` | Health endpoint |
| `test_trending_empty` | Empty Redis → empty response |
| `test_trending_with_scores` | Redis + DB → ranked list |
| `test_trending_skips_non_ready_videos` | Ghost Redis entries skipped |
| `test_trending_limit_query_param` | `?limit=5` → `ZREVRANGE 0 4` |
| `test_recommendations_empty_history` | No history → 100% trending |
| `test_recommendations_blends_trending_and_creator` | Hybrid blend + exclusion |

---

## 14. How It Fits in the Full Pipeline

```
[Phase 8a: event-ingestion]
POST /events/interaction
        │ publishes
        ▼
[Kafka topic: viewer-interaction-events]
        │ consumes
        ▼
[trending-service Kafka consumer]
        │
        ├── ZINCRBY trending:scores → Redis DB 4
        └── upsert watch_history  → PostgreSQL (on PLAY)

[Every hour]
trending-service decay loop
        │
        └── multiply all scores × 0.9 → Redis DB 4

[Frontend request]
GET /trending
        │
        ├── ZREVRANGE → Redis DB 4 (top N)
        └── SELECT videos WHERE id IN (...) → PostgreSQL

GET /trending/recommendations/{userId}
        │
        ├── ZREVRANGE → Redis (trending candidates)
        ├── SELECT watch_history WHERE user_id = ? → PostgreSQL
        ├── filter out watched videos
        ├── SELECT videos WHERE creator_id IN (...) → PostgreSQL
        └── merge 60/40
```

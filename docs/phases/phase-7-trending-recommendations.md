# Phase 7 — Trending & Recommendation Service

## Goal
A FastAPI microservice that maintains a real-time trending leaderboard and provides basic video recommendations. Trending scores are driven by viewer interaction events consumed from Kafka, stored in a Redis sorted set. Recommendations combine personal watch history with trending boost.

---

## Service Details

| Property | Value |
|---|---|
| Service name | `trending-service` |
| Port | `8005` |
| Framework | FastAPI + Kafka consumer (background) |
| Cache | Redis sorted set (`trending:videos`) |
| Database | PostgreSQL (watch history) |

---

## Folder Structure

```
services/trending-service/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py
    ├── config.py
    ├── database.py
    ├── redis_client.py
    ├── consumer.py          ← Kafka consumer for viewer-interaction-events
    ├── exceptions.py        ← service-specific exceptions
    ├── logger.py            ← MongoDB ErrorLogger instance
    ├── trending/
    │   ├── router.py        ← GET /trending
    │   ├── service.py       ← Redis sorted set operations
    │   ├── repository.py    ← DB queries
    │   └── cache.py         ← Redis operations
    └── recommendations/
        ├── router.py        ← GET /recommendations/:userId
        ├── service.py       ← recommendation logic
        ├── repository.py    ← DB queries
        └── cache.py         ← Redis operations
```

---

## Trending System

### How It Works

Every viewer interaction (play, pause, rewind, seek) increments the trending score for that video. More interactions = higher score = higher trending rank.

```
Kafka topic: viewer-interaction-events
     │
     ▼  (consumer group: trending-service-group)
Trending Service Consumer
     │
     ▼
ZINCRBY trending:videos <score_delta> <videoId>
(Redis sorted set, higher score = more trending)
```

### Score Delta by Event Type

| Event | Score Delta | Reasoning |
|---|---|---|
| `PLAY` | +1 | Basic engagement |
| `PAUSE` | +0.5 | Viewer paused to think |
| `REWIND` | +3 | High-interest signal |
| `SEEK` (forward) | +0.5 | Navigation |
| `SEEK` (backward) | +2 | Rewatch signal |
| `BUFFER` | -0.5 | Bad experience penalty |

### Redis Sorted Set Design

```
Key: trending:videos
Type: Sorted Set
Member: videoId (UUID)
Score: cumulative interaction weight

Commands:
  ZINCRBY trending:videos 3 "uuid-of-video"    ← on REWIND event
  ZREVRANGE trending:videos 0 9 WITHSCORES     ← top 10 trending
```

### Score Decay

To prevent old viral videos from staying at the top forever, scores are decayed hourly. This is a **required scheduled task** started in the lifespan hook:

```python
# app/main.py — lifespan startup
async def decay_scores():
    while True:
        await asyncio.sleep(3600)   # run every hour
        members = await redis.zrangebyscore("trending:videos", "-inf", "+inf", withscores=True)
        for video_id, score in members:
            await redis.zadd("trending:videos", {video_id: score * 0.9})

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    asyncio.create_task(consumer.consume())
    asyncio.create_task(decay_scores())   # ← hourly 0.9× multiplier
    yield
    await redis_client.close()
```

---

## API Endpoints

```
GET /trending
  Query: limit=10 (default), page=1
  Response:
  {
    "items": [
      { "videoId": "uuid", "title": "...", "thumbnail_url": "...",
        "score": 4821.5, "rank": 1 },
      ...
    ],
    "total": 10
  }
  Cache: Redis ZREVRANGE (sub-ms read, no additional cache needed)
  Errors: none (public endpoint)

GET /recommendations/:userId
  Response:
  {
    "items": [
      { "videoId": "uuid", "title": "...", "reason": "trending" | "watch_history" }
    ]
  }
  Logic: see below
  Errors:
    401 UNAUTHORIZED — no session cookie / expired session
```

---

## Recommendation Logic

Simple hybrid approach — no ML model required:

```
1. Get user's last 20 watched video IDs from PostgreSQL (watch_history)
2. Get top 20 trending video IDs from Redis sorted set
3. Remove already-watched videos from trending list
4. Combine: 60% trending, 40% watch-history-based (other videos by same creators)
5. Return top 10, annotated with reason
```

```python
async def get_recommendations(user_id: str) -> list:
    watched_ids  = await get_watch_history(user_id, limit=20)
    trending_ids = await redis.zrevrange("trending:videos", 0, 19)
    
    # Filter out already watched
    unseen_trending = [v for v in trending_ids if v not in watched_ids]
    
    # Get creator-based suggestions from watch history
    creator_videos = await get_videos_by_same_creators(watched_ids, exclude=watched_ids)
    
    # Merge and return
    results = unseen_trending[:6] + creator_videos[:4]
    return results[:10]
```

---

## PostgreSQL Schema

```sql
CREATE TABLE watch_history (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES users(id),
    video_id   UUID NOT NULL REFERENCES videos(id),
    watched_at TIMESTAMP DEFAULT NOW(),
    watch_pct  DECIMAL(5,2),   -- percentage of video watched (0.0 - 100.0)
    UNIQUE(user_id, video_id)  -- upsert on re-watch
);

CREATE INDEX idx_watch_history_user ON watch_history(user_id, watched_at DESC);
```

Watch history is populated by the Event Ingestion Service (Phase 8a) as a side-effect of receiving `PLAY` events.

---

## Watch History Population

The Trending Service consumer, in addition to updating Redis trending scores, also upserts a row into the `watch_history` PostgreSQL table whenever it receives a `PLAY` event. This makes the Trending Service the authoritative writer for watch history.

```python
# consumer.py — inside consume loop
if event["eventType"] == "PLAY":
    await db.execute(
        """
        INSERT INTO watch_history (user_id, video_id, watched_at, watch_pct)
        VALUES (:user_id, :video_id, NOW(), 0)
        ON CONFLICT (user_id, video_id)
        DO UPDATE SET watched_at = NOW()
        """,
        {"user_id": event["userId"], "video_id": event["videoId"]}
    )
```

This upsert ensures that:
- First play creates the row.
- Re-watches update `watched_at` to the most recent timestamp (enabling recency-based recommendations).

---

## Kafka Consumer

```python
# consumer.py
SCORE_DELTAS = {
    "PLAY": 1.0,
    "PAUSE": 0.5,
    "REWIND": 3.0,
    "SEEK": 1.0,
    "BUFFER": -0.5,
}

async def consume():
    consumer = AIOKafkaConsumer(
        "viewer-interaction-events",
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="trending-service-group",
        value_deserializer=lambda v: json.loads(v.decode())
    )
    await consumer.start()
    async for msg in consumer:
        event = msg.value
        delta = SCORE_DELTAS.get(event["eventType"], 0)
        if delta != 0:
            await redis.zincrby("trending:videos", delta, event["videoId"])
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| Kafka consume | Async loop | Non-blocking |
| Redis ZINCRBY | Async (await) | Non-blocking — critical hot path |
| GET /trending | Sync Redis read | ZREVRANGE is sub-ms, sync is fine |
| GET /recommendations | Async (await) | Involves PostgreSQL lookup |
| Score decay job | Async scheduled | Background task, no user waits |

---

## References Shared Patterns

This service follows all conventions defined in [`docs/phases/shared-patterns.md`](shared-patterns.md):

- **Folder structure** — layered `router / service / repository / cache` per domain (§8)
- **Standard main.py** — lifespan, exception handlers, `AppException` mapping (§3)
- **Standard config.py** — `BaseSettings`, `POSTGRES_URL` property (§4)
- **Response envelope** — `SuccessResponse[T]` / `ErrorResponse` from `shared/schemas.py` (§5)
- **Error codes** — `UNAUTHORIZED` (401) from `shared/exceptions.AuthError` (§5)
- **MongoDB error logger** — unhandled exceptions written to `error_logs` collection via `logger.py` (§7)
- **Kafka partition key** — `key=video_id.encode()` on all producer sends (§6)

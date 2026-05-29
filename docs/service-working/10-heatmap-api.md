# Heatmap API — Complete Technical Reference

## 1. What Is This Service?

The **heatmap-api** is the **read-only HTTP facade** for the heatmap feature. It exposes three
endpoints that let the frontend overlay engagement data on the video progress bar, show a live
"hot spot" pulse, and surface the most-replayed moments to viewers or creators.

**All data was written by heatmap-aggregator** — this service only reads. The two services share
the same Redis DB 6 and MongoDB `heatmaps` database with no HTTP calls between them.

**Port:** `8008` (internal Docker network: `heatmap-api:8008`)  
**Cache:** Redis DB 6 (`redis://redis:6379/6`) — live bucket keys (read-only here)  
**Database:** MongoDB (`heatmaps` DB, `heatmap_buckets` collection — read-only here)  
**Framework:** FastAPI + motor (async MongoDB driver) + redis[asyncio]

---

## 2. Folder Structure

```
heatmap-api/
├── app/
│   ├── main.py                ← FastAPI app, lifespan hooks, global error handlers
│   ├── config.py              ← Pydantic-Settings (REDIS_URL, MONGO_URL, MONGO_DB, BUCKET_SIZE)
│   ├── redis_client.py        ← Singleton Redis connection + get_redis()
│   ├── mongo_client.py        ← Motor singleton + get_db()
│   │
│   └── heatmap/               ← Heatmap domain
│       ├── handler/
│       │   └── router.py      ← 3 HTTP routes: /heatmap/{id}, /live, /highlights
│       ├── utils/
│       │   ├── service.py     ← Business logic: fetch → transform → build response
│       │   └── schemas.py     ← BucketItem, HeatmapResponse, HighlightsResponse, make_label()
│       └── dao/
│           └── repository.py  ← MongoDB queries: get_all_buckets, get_top_buckets
│
├── tests/
│   └── test_heatmap_api.py    ← 10 tests: label formatting, all 3 endpoints, health
├── Dockerfile
├── requirements.txt           ← motor==3.7.1, mongomock-motor==0.0.21
└── pytest.ini
```

---

## 3. Three-Layer Architecture

```
HTTP Request
    │
    ▼
handler/router.py       ← Receives request, calls service, wraps in SuccessResponse
    │                      Never queries Redis or MongoDB directly
    ▼
utils/service.py        ← Fetches data, transforms to response models, raises 404 if empty
    │
    ├──► Redis directly (for /live: key scan + get)
    └──► dao/repository.py ← MongoDB queries
```

**Layer rules:**
- `handler/router.py` → calls `utils/service.py` only. Returns `SuccessResponse[T]`.
- `utils/service.py` → calls `dao/repository.py` for MongoDB and Redis directly for live keys.
- `dao/repository.py` → raw Motor cursor queries only. No business logic.

> **Note:** `utils/service.py` accesses Redis directly (not via a `cache.py`) because the live
> heatmap operation is a key scan (`keys pattern`) — not a cacheable get. It is a read path with
> no write side effects.

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/6` | Redis DB 6 (shared with heatmap-aggregator) |
| `MONGO_URL` | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGO_DB` | `heatmaps` | Database name |
| `BUCKET_SIZE` | `5` | Width of each bucket in seconds (must match aggregator) |

---

## 5. Entry Point (main.py)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_redis()
    await connect_mongo()
    yield
    await close_mongo()
    await close_redis()
```

Simple startup — connect to Redis and MongoDB, then serve HTTP requests. No background tasks,
no Kafka consumer, no DB migrations.

---

## 6. Label Formatting (utils/schemas.py)

Every bucket in every response includes a human-readable `label` field:

```python
def make_label(bucket: int, bucket_size: int) -> str:
    """Convert a bucket start second into a MM:SS–MM:SS string."""
    def fmt(s: int) -> str:
        return f"{s // 60}:{s % 60:02d}"
    return f"{fmt(bucket)}–{fmt(bucket + bucket_size)}"
```

**Examples:**

| `bucket` | `bucket_size` | `label` |
|---|---|---|
| `0` | `5` | `0:00–0:05` |
| `5` | `5` | `0:05–0:10` |
| `60` | `5` | `1:00–1:05` |
| `140` | `5` | `2:20–2:25` |
| `3600` | `5` | `60:00–60:05` |

The frontend can display this directly in the video progress bar tooltip without any client-side
timestamp math.

---

## 7. API Endpoints

### Health Check

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service health check |

**Response:**
```json
{ "status": "ok", "service": "heatmap-api" }
```

---

### GET `/heatmap/{videoId}`

Returns the **all-time** engagement heatmap for a video from MongoDB.

**Auth Required:** No

**Path parameter:**
- `videoId` — UUID of the video

**Success Response — 200 OK:**
```json
{
  "data": {
    "video_id": "550e8400-e29b-41d4-a716-446655440002",
    "bucket_size": 5,
    "total_buckets": 3,
    "buckets": [
      { "bucket": 0,   "score": 2,  "label": "0:00–0:05" },
      { "bucket": 5,   "score": 8,  "label": "0:05–0:10" },
      { "bucket": 140, "score": 47, "label": "2:20–2:25" }
    ]
  }
}
```

**Error Responses:**

| Status | Error Code | Cause |
|---|---|---|
| 404 | `NOT_FOUND` | No interaction data recorded for this video |

**Internal Flow:**
```
GET /heatmap/{videoId}
    → handler/router.py → heatmap_service.get_heatmap(db, videoId)
        → repo.get_all_buckets(db, videoId)
            → db.heatmap_buckets.find({videoId: ...}).sort("bucket", 1)
        → if empty: raise NotFoundError → 404
        → build BucketItem list with make_label() for each bucket
    ← return SuccessResponse[HeatmapResponse]
```

---

### GET `/heatmap/{videoId}/live`

Returns the **last 5-minute** engagement heatmap from Redis.

**Auth Required:** No

**Path parameter:**
- `videoId` — UUID of the video

**Success Response — 200 OK** (with recent activity):
```json
{
  "data": {
    "video_id": "550e8400-e29b-41d4-a716-446655440002",
    "bucket_size": 5,
    "total_buckets": 1,
    "buckets": [
      { "bucket": 140, "score": 12, "label": "2:20–2:25" }
    ]
  }
}
```

**Success Response — 200 OK** (no recent activity):
```json
{
  "data": {
    "video_id": "550e8400-e29b-41d4-a716-446655440002",
    "bucket_size": 5,
    "total_buckets": 0,
    "buckets": []
  }
}
```

> **No 404 is raised** for an empty live heatmap. Zero activity is a valid state — the video
> may simply have no viewers right now. Only the all-time endpoint raises 404.

**Internal Flow:**
```
GET /heatmap/{videoId}/live
    → handler/router.py → heatmap_service.get_live_heatmap(redis, videoId)
        → redis.keys("heatmap:{videoId}:live:*")
        → for each key (sorted):
            → redis.get(key)  → score string
            → parse bucket from key suffix: "heatmap:vid:live:140" → 140
            → build BucketItem with make_label()
    ← return SuccessResponse[HeatmapResponse]
```

**Why `redis.keys(pattern)`?**  
The aggregator creates one key per active bucket. We don't know ahead of time how many buckets a
video has — we scan for them. For production use, `SCAN` with a cursor would be preferred over
`KEYS` to avoid blocking Redis, but for this project scale `KEYS` is acceptable.

---

### GET `/heatmap/{videoId}/highlights`

Returns the **top N most-replayed segments** for a video, sorted by score descending.

**Auth Required:** No

**Path parameter:**
- `videoId` — UUID of the video

**Query parameters:**
- `limit` (int, 1–20, default 5) — how many top buckets to return

**Success Response — 200 OK:**
```json
{
  "data": {
    "video_id": "550e8400-e29b-41d4-a716-446655440002",
    "highlights": [
      { "bucket": 140, "score": 47, "label": "2:20–2:25" },
      { "bucket": 60,  "score": 20, "label": "1:00–1:05" },
      { "bucket": 5,   "score": 8,  "label": "0:05–0:10" }
    ]
  }
}
```

**Error Responses:**

| Status | Error Code | Cause |
|---|---|---|
| 404 | `NOT_FOUND` | No interaction data recorded for this video |

**Internal Flow:**
```
GET /heatmap/{videoId}/highlights?limit=5
    → handler/router.py → heatmap_service.get_highlights(db, videoId, limit)
        → repo.get_top_buckets(db, videoId, limit)
            → db.heatmap_buckets.find({videoId: ...})
                             .sort("score", -1)
                             .limit(limit)
        → if empty: raise NotFoundError → 404
        → build BucketItem list with make_label()
    ← return SuccessResponse[HighlightsResponse]
```

---

#### GET `/heatmap/{video_id}/stream` — SSE Live Feed

**Auth Required:** Yes (session cookie) — creator only  
**Protocol:** Server-Sent Events (text/event-stream)

Streams live heatmap snapshots to connected clients every few seconds via `sse-starlette`. The frontend's `useHeatmapSSE` hook connects to this endpoint to update the heatmap chart in real time on the Dashboard and Player pages.

**Path Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `video_id` | string | Video UUID |

**SSE Event Format:**
```
data: {"video_id": "abc-123", "segments": [{"segment_id": 0, "count": 12, "label": "0:00–0:05"}, ...]}

data: {"video_id": "abc-123", "segments": [...]}
```

Each event is a JSON-encoded object that the frontend normalises via `heatmap.js` → `normBucket` mapping (`bucket → segment_id`, `score → count`).

**Internal Flow:**
```
GET /heatmap/{video_id}/stream
    → auth check: must be creator (403 if not)
    → EventSourceResponse (sse-starlette)
        → generator: loop every N seconds
            → heatmap_service.get_heatmap(db, video_id)
            → yield JSON snapshot
```

---

## 8. Response Schemas (utils/schemas.py)

```python
class BucketItem(BaseModel):
    bucket: int   # start second of the 5-second window (e.g. 140)
    score: int    # cumulative weighted engagement score
    label: str    # human-readable "MM:SS–MM:SS" (e.g. "2:20–2:25")

class HeatmapResponse(BaseModel):
    video_id: str
    bucket_size: int        # always 5
    total_buckets: int
    buckets: list[BucketItem]

class HighlightsResponse(BaseModel):
    video_id: str
    highlights: list[BucketItem]  # top N, sorted by score desc
```

All endpoints wrap responses in `SuccessResponse[T]` from `shared.schemas`:
```json
{ "data": { ... } }
```

---

## 9. MongoDB Queries (dao/repository.py)

```python
async def get_all_buckets(db, video_id: str) -> list[dict]:
    """All buckets sorted by position (ascending)."""
    cursor = db.heatmap_buckets.find(
        {"videoId": video_id},
        {"_id": 0, "bucket": 1, "score": 1},
    ).sort("bucket", 1)
    return await cursor.to_list(length=None)

async def get_top_buckets(db, video_id: str, limit: int = 5) -> list[dict]:
    """Top N buckets ranked by score (descending)."""
    cursor = db.heatmap_buckets.find(
        {"videoId": video_id},
        {"_id": 0, "bucket": 1, "score": 1},
    ).sort("score", -1).limit(limit)
    return await cursor.to_list(length=limit)
```

**Projection `{"_id": 0, ...}`** — excludes MongoDB's internal `_id` field from results.
This keeps responses clean and avoids `ObjectId` serialisation issues.

---

## 10. Error Response Format

All errors follow this envelope:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "detail": null
}
```

| Error Code | HTTP Status | When |
|---|---|---|
| `NOT_FOUND` | 404 | No heatmap data for this video (all-time or highlights) |
| `VALIDATION_ERROR` | 422 | `limit` out of range (e.g. `limit=0`) |

---

## 11. Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
```

**Key points:**
- No database migrations — this service only reads, never writes
- `shared/` module bind-mounted from host via docker-compose
- Starts on port 8008

---

## 12. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `redis[asyncio]` | 5.0.3 | Async Redis client (live heatmap reads) |
| `motor` | 3.7.1 | Async MongoDB driver |
| `pydantic[email]` | 2.6.4 | Response schema validation |
| `pydantic-settings` | 2.2.1 | Config from environment |
| `mongomock-motor` | 0.0.21 | In-memory MongoDB for tests |

> **Important:** `motor==3.7.1` is required (same as heatmap-aggregator). Older versions fail
> with `ImportError: cannot import name '_QUERY_OPTIONS'` due to pymongo 4.x incompatibility.

---

## 13. Testing

**Test runner:** `pytest` with `pytest-asyncio`

**Test strategy:**
- **MongoDB:** `AsyncMock` + `MagicMock` for cursor chaining (`.find().sort().to_list()`)
- **Redis:** `AsyncMock` for `keys()` and `get()` — return values control test scenarios
- **FastAPI `dependency_overrides`:** Injects `mock_redis` and `mock_db`
- **Label formatting:** Pure unit tests — no mocks needed

**Run tests:**
```bash
cd backend/heatmap-api
python -m pytest tests/ -v
# Expected: 10 passed
```

**Test coverage:**

| Test | What it covers |
|---|---|
| `test_make_label_zero` | `make_label(0, 5)` → `"0:00–0:05"` |
| `test_make_label_minute_boundary` | `make_label(60, 5)` → `"1:00–1:05"` |
| `test_make_label_mid_video` | `make_label(140, 5)` → `"2:20–2:25"` |
| `test_make_label_large` | `make_label(3600, 5)` → `"60:00–60:05"` |
| `test_get_heatmap_returns_data` | MongoDB returns 2 buckets → 200, correct labels |
| `test_get_heatmap_not_found` | MongoDB returns [] → 404 |
| `test_get_live_heatmap_empty` | Redis keys=[] → 200, total_buckets=0 |
| `test_get_live_heatmap_with_data` | Redis key="live:140", score="12" → 200, bucket=140 |
| `test_get_highlights` | MongoDB returns top 2 → 200, score=47 first |
| `test_health` | `GET /health` → `{"status": "ok"}` |

---

## 14. How It Fits in the Full Pipeline

```
[heatmap-aggregator]               [heatmap-api]              [Frontend]
  writes every event         reads on HTTP request          displays overlay
        │                              │                           │
        │── Redis DB 6 ──────────────►│── GET /heatmap/{id}/live ─►│
        │   heatmap:vid:live:*        │   scan live:* keys         │
        │                             │                           │
        │── MongoDB heatmaps ────────►│── GET /heatmap/{id}       ─►│
            heatmap_buckets           │   all-time buckets         │
                                      │                           │
                                      │── GET /heatmap/{id}/      ─►│
                                          highlights               │
                                          top N by score           │
```

---

## 15. Data Flow Diagram

```
CLIENT               NGINX            HEATMAP-API            REDIS(DB6)     MONGODB
  │                    │                   │                      │             │
  │── GET /heatmap/x ──►                  │                      │             │
  │                    │──► router.py      │                      │             │
  │                    │      └─ service.get_heatmap(db, x)                    │
  │                    │           └─ repo.get_all_buckets() ─────────────────►│
  │                    │               find({videoId:x}).sort(bucket,1)        │
  │◄── 200 {data:{...}} ┤                  │                      │             │
  │                    │                   │                      │             │
  │── GET /heatmap/x/live ►                │                      │             │
  │                    │──► router.py      │                      │             │
  │                    │      └─ service.get_live_heatmap(redis, x)            │
  │                    │           └─ redis.keys("heatmap:x:live:*") ─────────►│
  │                    │           └─ redis.get(key) for each ────────────────►│
  │◄── 200 {data:{...}} ┤                  │                      │             │
  │                    │                   │                      │             │
  │── GET /heatmap/x/highlights ►          │                      │             │
  │                    │──► router.py      │                      │             │
  │                    │      └─ service.get_highlights(db, x, 5)              │
  │                    │           └─ repo.get_top_buckets() ─────────────────►│
  │                    │               find({videoId:x}).sort(score,-1).limit(5)│
  │◄── 200 {data:{...}} ┤                  │                      │             │
```

---

## 16. Design Decisions

1. **Read-only service:** This service never writes to Redis or MongoDB. The strict read/write
   separation means the aggregator can be updated or restarted without affecting the API, and
   the API can be scaled independently for read traffic.

2. **Live endpoint returns 200 with empty list (not 404):** An empty live heatmap is a valid
   state — the video has no recent viewers. Returning 404 would mislead the frontend into
   thinking the video doesn't exist or has no heatmap at all. The all-time endpoint *does* raise
   404 because if there's no historical data, the video has truly never been interacted with.

3. **MongoDB `_id` excluded from projections:** MongoDB auto-generates `_id` as an `ObjectId`
   which is not JSON-serialisable by default. Excluding it with `{"_id": 0}` avoids the need for
   a custom serialiser and keeps responses clean.

4. **`make_label` in schemas (not utils):** The label function is co-located with the schemas
   it enriches. `BucketItem` always has a `label` — coupling them makes it impossible to create
   a `BucketItem` without a label, which is the desired invariant.

5. **No auth on heatmap endpoints:** Heatmap data is not personally identifiable — it shows
   aggregate engagement, not individual viewer behaviour. Making it publicly readable enables
   use cases like embedding heatmaps in external players without authentication overhead.

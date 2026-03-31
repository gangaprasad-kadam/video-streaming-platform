# 📋 Phase 8 — Viewer Behavior Heatmap Engine 🔥 (Unique Feature)

> **Goal:** Three coordinated services that form the real-time viewer heatmap system:
> - **8a** `event-ingestion` (port 8006) — accepts viewer micro-interactions, returns 202 immediately
> - **8b** `heatmap-aggregator` (no port) — buckets events into 5-second segments in Redis
> - **8c** `heatmap-api` (port 8007) — serves heatmap to creator dashboard via REST + SSE

**Reference doc:** [`docs/phases/phase-8-heatmap-engine.md`](../phases/phase-8-heatmap-engine.md)
**Unique feature doc:** [`docs/unique-feature.md`](../unique-feature.md)
**Depends on:** Phase 1 ✅ (Kafka topics), Phase 2 ✅ (users), Phase 3 ✅ (videos)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

### 8a — Event Ingestion Service

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure (event-ingestion) | ⬜ |
| 2 | Write `requirements.txt` | ⬜ |
| 3 | Write `Dockerfile` | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/redis_client.py` + `app/kafka_producer.py` | ⬜ |
| 6 | Write `app/events/schemas.py` | ⬜ |
| 7 | Write `app/events/cache.py` (rate limiting) | ⬜ |
| 8 | Verify no `repository.py` needed (stateless service) | ⬜ |
| 9 | Write `app/events/service.py` | ⬜ |
| 10 | Write `app/events/router.py` | ⬜ |
| 11 | Write `app/main.py` | ⬜ |
| 12 | Add to `docker-compose.yml` | ⬜ |
| 13 | Write `tests/test_event_ingestion.py` + run | ⬜ |

### 8b — Heatmap Aggregator

| # | Task | Status |
|---|---|---|
| 14 | Create folder structure (heatmap-aggregator) | ⬜ |
| 15 | Write `requirements.txt` + `Dockerfile` | ⬜ |
| 16 | Write `app/config.py` | ⬜ |
| 17 | Write `app/models.py` (viewer_events + snapshots + alerts) | ⬜ |
| 18 | Set up Alembic + migrations | ⬜ |
| 19 | Write `app/heatmap/cache.py` (Redis HINCRBY pattern) | ⬜ |
| 20 | Write `app/heatmap/repository.py` | ⬜ |
| 21 | Write `app/aggregator.py` (segment bucketing) | ⬜ |
| 22 | Write `app/viral_detector.py` | ⬜ |
| 23 | Write `app/flusher.py` (hourly + weekly tasks) | ⬜ |
| 24 | Write `app/consumer.py` | ⬜ |
| 25 | Write `app/main.py` | ⬜ |
| 26 | Add to `docker-compose.yml` | ⬜ |
| 27 | Write `tests/test_heatmap_aggregator.py` + run | ⬜ |

### 8c — Heatmap API

| # | Task | Status |
|---|---|---|
| 28 | Create folder structure (heatmap-api) | ⬜ |
| 29 | Write `requirements.txt` + `Dockerfile` | ⬜ |
| 30 | Write `app/config.py` | ⬜ |
| 31 | Write `app/exceptions.py` | ⬜ |
| 32 | Write `app/heatmap/cache.py` (read segment keys + summary) | ⬜ |
| 33 | Write `app/heatmap/repository.py` (DB fallback reads) | ⬜ |
| 34 | Write `app/heatmap/service.py` | ⬜ |
| 35 | Write `app/heatmap/router.py` (REST + SSE) | ⬜ |
| 36 | Write `app/consumer.py` (heatmap-aggregated → Redis pub/sub) | ⬜ |
| 37 | Write `app/main.py` | ⬜ |
| 38 | Add to `docker-compose.yml` | ⬜ |
| 39 | Write `tests/test_heatmap_api.py` + run | ⬜ |

---

## Task Details

---

## 🟦 8a — Event Ingestion Service

---

### ✅ Task 1 — Create Folder Structure (event-ingestion)

```bash
mkdir -p services/event-ingestion/app/events \
         services/event-ingestion/tests
touch services/event-ingestion/app/__init__.py \
      services/event-ingestion/app/events/__init__.py \
      services/event-ingestion/tests/__init__.py
```

**Acceptance criteria:**
- [ ] `app/events/` and `tests/` exist with `__init__.py`

---

### ✅ Task 2 — Write `requirements.txt` (event-ingestion)

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
aiokafka==0.10.0
redis[asyncio]==5.0.3
pydantic-settings==2.2.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
fakeredis==2.21.3
```

**Note:** No `alembic` and no `sqlalchemy`/`asyncpg` — this service is stateless (Redis + Kafka only, no DB writes). The `watch_history` table is owned and written by **trending-service** (Phase 7).

**Acceptance criteria:**
- [ ] `aiokafka` and `redis[asyncio]` included, no alembic, no sqlalchemy

---

### ✅ Task 3 — Write `Dockerfile` (event-ingestion)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
```

**Note:** No alembic in CMD — this service does not own any tables.

**Acceptance criteria:**
- [ ] Port is `8006`, no alembic

---

### ✅ Task 4 — Write `app/config.py` (event-ingestion)

**Settings:**

| Setting | Env var | Default |
|---|---|---|
| `redis_host/port` | 2 Redis vars | — |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `rate_limit_max_events` | `RATE_LIMIT_MAX_EVENTS` | `100` |
| `rate_limit_window_seconds` | `RATE_LIMIT_WINDOW_SECONDS` | `60` |

**Note:** No PostgreSQL config — this service has no DB of its own.

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.config import settings
assert settings.rate_limit_max_events == 100
assert settings.rate_limit_window_seconds == 60
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] Rate limit settings configurable, test exits 0

---

### ✅ Task 5 — Write `app/redis_client.py` + `app/kafka_producer.py`

**`redis_client.py`:** Same pattern as other services. Expose `connect_redis()`, `close_redis()`, `get_redis()`.

**`kafka_producer.py`:**

```python
# Expose: start_producer(), stop_producer(), publish(topic, key, value)
# value_serializer: json.dumps → bytes
# key: videoId.encode() (partition by videoId)
```

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.redis_client import get_redis
from app.kafka_producer import start_producer, stop_producer, publish
import inspect
assert inspect.isasyncgenfunction(get_redis)
for fn in [start_producer, stop_producer, publish]:
    assert inspect.iscoroutinefunction(fn)
print('Redis + Kafka OK')
"
```

**Acceptance criteria:**
- [ ] Both modules importable
- [ ] `publish` uses `key=video_id.encode()` (partition by videoId)
- [ ] Test exits 0

---

### ✅ Task 6 — Write `app/events/schemas.py`

**File:** `services/event-ingestion/app/events/schemas.py`

**Schema: `InteractionEvent`**

| Field | Type | Required | Notes |
|---|---|---|---|
| `videoId` | `UUID` | ✅ | — |
| `eventType` | `Literal['PLAY','PAUSE','REWIND','SEEK','SKIP','SPEED_CHANGE','BUFFER']` | ✅ | Enum validation |
| `videoTs` | `float` | ✅ | Position in seconds (≥ 0) |
| `seekFrom` | `float \| None` | ❌ | Only for SEEK events |
| `clientTime` | `int` | ✅ | Unix timestamp |

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.events.schemas import InteractionEvent
from pydantic import ValidationError
# Valid
e = InteractionEvent(videoId='00000000-0000-0000-0000-000000000001', eventType='REWIND', videoTs=142.5, clientTime=1711882140)
assert e.eventType == 'REWIND'
# Invalid eventType
try:
    InteractionEvent(videoId='00000000-0000-0000-0000-000000000001', eventType='INVALID', videoTs=0, clientTime=0)
    assert False
except ValidationError:
    pass
print('Event schema OK')
"
```

**Acceptance criteria:**
- [ ] `eventType` validated against allowed values
- [ ] `videoTs` ≥ 0 validated
- [ ] Test exits 0

---

### ✅ Task 7 — Write `app/events/cache.py` (Rate Limiting)

**File:** `services/event-ingestion/app/events/cache.py`

**What:** Redis token bucket — counts events per session per 60-second window.

**Function: `check_rate_limit(redis, session_id)`**

```python
async def check_rate_limit(redis, session_id: str) -> None:
    """
    Increments counter. Sets 60s TTL on first request.
    Raises RateLimitError if count exceeds settings.rate_limit_max_events.
    """
    key = f"ratelimit:events:{session_id}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, settings.rate_limit_window_seconds)
    if current > settings.rate_limit_max_events:
        raise RateLimitError()
```

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.events.cache import check_rate_limit
import inspect
assert inspect.iscoroutinefunction(check_rate_limit)
print('Rate limit cache OK')
"
```

**Acceptance criteria:**
- [ ] Uses `ratelimit:events:` key prefix
- [ ] TTL set to `rate_limit_window_seconds` on first increment
- [ ] Raises `RateLimitError` when count > max
- [ ] `async def`, test exits 0

---

### ✅ Task 8 — Verify no `repository.py` needed (stateless service)

**What:** Event-ingestion is a stateless pass-through service. It has **no database writes**:
- Rate limiting → Redis (`cache.py`)
- Event publishing → Kafka (`kafka_producer.py`)
- `watch_history` upsert → handled by **trending-service** (Phase 7), not here

No `repository.py`, no `database.py`, no SQLAlchemy dependency.

**Test / Verify:**
```bash
cd services/event-ingestion
# Confirm no DB-related files exist
test ! -f app/events/repository.py && test ! -f app/database.py && echo "✅ No DB files — correct"
```

**Acceptance criteria:**
- [ ] No `repository.py` or `database.py` in event-ingestion
- [ ] No `sqlalchemy` or `asyncpg` in `requirements.txt`
- [ ] Service only depends on Redis + Kafka

---

### ✅ Task 9 — Write `app/events/service.py`

**File:** `services/event-ingestion/app/events/service.py`

**Function: `handle_event(event, user_id, session_id, background_tasks)`**

```python
async def handle_event(event, user_id, session_id, background_tasks):
    # 1. Add Kafka publish to background tasks
    background_tasks.add_task(
        kafka_producer.publish,
        "viewer-interaction-events",
        str(event.videoId),
        {
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

> **Note:** Event-ingestion does NOT write to `watch_history`. That is handled
> by the **trending-service** consumer (Phase 7) when it processes PLAY events.

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.events.service import handle_event
import inspect
assert inspect.iscoroutinefunction(handle_event)
print('Service OK')
"
```

**Acceptance criteria:**
- [ ] `async def`
- [ ] Kafka publish added to `BackgroundTasks` (not awaited directly)
- [ ] No direct DB writes in this service
- [ ] Test exits 0

---

### ✅ Task 10 — Write `app/events/router.py`

**File:** `services/event-ingestion/app/events/router.py`

**Endpoint:**

| Method | Path | Auth | Response |
|---|---|---|---|
| `POST` | `/events/interaction` | Required | **202 Accepted** (not 200/201) |

**Critical:** Return 202 immediately. Never `await` Kafka publish directly.

```python
@router.post("/events/interaction", status_code=202)
async def ingest_event(
    event: InteractionEvent,
    background_tasks: BackgroundTasks,
    request: Request,
    redis=Depends(get_redis),
    current_user: str = Depends(get_current_user)
):
    session_id = request.cookies.get("session_id")
    await cache.check_rate_limit(redis, session_id)
    await service.handle_event(event, current_user, session_id, background_tasks)
    return {"message": "accepted"}
```

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.events.router import router
routes = {r.path: r for r in router.routes}
assert '/events/interaction' in routes
assert routes['/events/interaction'].status_code == 202
print('Router OK')
"
```

**Acceptance criteria:**
- [ ] Status code is **202** (not 200/201)
- [ ] Rate limit check happens before Kafka publish
- [ ] Kafka publish is a BackgroundTask (non-blocking)
- [ ] Test exits 0

---

### ✅ Task 11 — Write `app/main.py` (event-ingestion)

**Lifespan startup:** `connect_redis()` + `start_producer()`
**Lifespan shutdown:** `stop_producer()` + `close_redis()`

**Include router:**
```python
app.include_router(events_router, prefix="/events", tags=["events"])
```

**Test / Verify:**
```bash
cd services/event-ingestion
python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/events/interaction' in paths
print('main.py OK')
"
```

**Acceptance criteria:**
- [ ] Kafka producer started/stopped in lifespan
- [ ] Route mounted, test exits 0

---

### ✅ Task 12 — Add to `docker-compose.yml` (event-ingestion)

```yaml
event-ingestion:
  build: ./services/event-ingestion
  ports:
    - "8006:8006"
  environment:
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    RATE_LIMIT_MAX_EVENTS: 100
    RATE_LIMIT_WINDOW_SECONDS: 60
  volumes:
    - ./services/shared:/app/shared:ro
  depends_on:
    redis:
      condition: service_healthy
    kafka:
      condition: service_healthy
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose up -d event-ingestion
sleep 5
curl -f http://localhost:8006/docs
```

**Acceptance criteria:**
- [ ] `GET http://localhost:8006/docs` returns 200

---

### ✅ Task 13 — Write `tests/test_event_ingestion.py` + Run

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_post_event_returns_202_immediately` | Valid event + auth cookie | **202** response |
| `test_post_event_requires_auth` | No session cookie | 401 UNAUTHORIZED |
| `test_rate_limit_exceeded_returns_429` | 101 events in 60s window | 429 RATE_LIMIT_EXCEEDED |
| `test_event_published_to_kafka` | Valid event | `mock_kafka.publish` called with correct topic + payload |
| `test_invalid_event_type_returns_422` | `eventType: "INVALID"` | 422 VALIDATION_ERROR |

**Run:**
```bash
cd services/event-ingestion
pytest tests/test_event_ingestion.py -v
```

**Acceptance criteria:**
- [ ] All 6 tests pass ✅
- [ ] 202 status verified (not 200)
- [ ] Rate limit test passes
- [ ] Kafka mock verifies correct topic (`viewer-interaction-events`) and key (videoId)

---

## 🟩 8b — Heatmap Aggregator

---

### ✅ Task 14 — Create Folder Structure (heatmap-aggregator)

```bash
mkdir -p services/heatmap-aggregator/app/heatmap \
         services/heatmap-aggregator/tests
touch services/heatmap-aggregator/app/__init__.py \
      services/heatmap-aggregator/app/heatmap/__init__.py \
      services/heatmap-aggregator/tests/__init__.py
```

**Acceptance criteria:**
- [ ] All dirs + `__init__.py` exist

---

### ✅ Task 15 — Write `requirements.txt` + `Dockerfile` (heatmap-aggregator)

**`requirements.txt`:**
```
aiokafka==0.10.0
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.28
pydantic-settings==2.2.1
redis[asyncio]==5.0.3
alembic==1.13.1
motor==3.3.2
pytest==8.1.1
pytest-asyncio==0.23.5
fakeredis==2.21.3
```

**`Dockerfile`:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && python -m app.main"]
```

**Acceptance criteria:**
- [ ] Alembic runs before starting consumer

---

### ✅ Task 16 — Write `app/config.py` (heatmap-aggregator)

**Settings:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_*` | 5 PG vars | — |
| `redis_*` | 2 Redis vars | — |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `mongo_*` | 4 Mongo vars | — |
| `segment_size` | `SEGMENT_SIZE` | `5` |
| `live_key_ttl` | `LIVE_KEY_TTL` | `600` |
| `total_key_ttl` | `TOTAL_KEY_TTL` | `604800` |
| `viral_sigma_threshold` | `VIRAL_SIGMA_THRESHOLD` | `3.0` |

**Test / Verify:**
```bash
cd services/heatmap-aggregator
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
MONGO_USER=admin MONGO_PASSWORD=secret \
python -c "
from app.config import settings
assert settings.segment_size == 5
assert settings.viral_sigma_threshold == 3.0
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] `segment_size=5` (seconds per bucket), configurable, test exits 0

---

### ✅ Task 17 — Write `app/models.py` (heatmap-aggregator)

**3 models:**

**`ViewerEvent`** (`viewer_events` table — partitioned by month in production):

| Column | Type |
|---|---|
| `id` | BigSerial PK |
| `video_id` | UUID, NOT NULL |
| `user_id` | UUID, NOT NULL |
| `session_id` | String(36) |
| `event_type` | String(20) |
| `video_ts` | Numeric(10,2) |
| `seek_from` | Numeric(10,2), nullable |
| `ingested_at` | DateTime |

**`VideoHeatmapSnapshot`** (`video_heatmap_snapshots` table):

| Column | Type |
|---|---|
| `id` | UUID PK |
| `video_id` | UUID, NOT NULL |
| `segment_id` | Integer, NOT NULL |
| `counts` | JSON — `{eventType: count}` |
| `total_interactions` | Integer |
| `snapshot_at` | DateTime, default `now()` |

**`ViralSegmentAlert`** (`viral_segment_alerts` table):

| Column | Type |
|---|---|
| `id` | UUID PK |
| `video_id` | UUID, NOT NULL |
| `segment_id` | Integer, NOT NULL |
| `metric` | String(50) |
| `value` | Numeric |
| `sigma` | Numeric |
| `alerted_at` | DateTime, default `now()` |

**Test / Verify:**
```bash
cd services/heatmap-aggregator
python -c "
from app.models import ViewerEvent, VideoHeatmapSnapshot, ViralSegmentAlert
for m in [ViewerEvent, VideoHeatmapSnapshot, ViralSegmentAlert]:
    print(f'{m.__tablename__}: {[c.name for c in m.__table__.columns]}')
print('Models OK')
"
```

**Acceptance criteria:**
- [ ] All 3 models importable with correct columns

---

### ✅ Task 18 — Set Up Alembic + Create Migrations

```bash
cd services/heatmap-aggregator
alembic init alembic
# Edit env.py as usual
alembic revision --autogenerate -m "create_heatmap_tables"
```

**Test / Verify:**
```bash
alembic upgrade head
docker compose exec postgres psql -U admin -d videoplatform \
  -c "\dt viewer_events; \dt video_heatmap_snapshots; \dt viral_segment_alerts;"
```

**Acceptance criteria:**
- [ ] All 3 tables created, `alembic upgrade head` exits 0

---

### ✅ Task 19 — Write `app/heatmap/cache.py` (heatmap-aggregator)

**File:** `services/heatmap-aggregator/app/heatmap/cache.py`

**Redis key patterns:**

| Key | Op | TTL | Purpose |
|---|---|---|---|
| `heatmap:{vid}:live:{seg}` | `HINCRBY ... eventType 1` | 600s (10min) | Last 5-min window counts |
| `heatmap:{vid}:total:{seg}` | `HINCRBY ... eventType 1` | 604800s (7d) | All-time counts |
| `heatmap:{vid}:baseline:{seg}` | `HSET ... mean M stddev S` | — | Statistical baseline |

**Functions:**

| Function | Action |
|---|---|
| `record_event(redis, video_id, seg_id, event_type)` | `HINCRBY` on both live + total keys, set TTLs |
| `get_total_counts(redis, video_id, seg_id)` | `HGETALL heatmap:{vid}:total:{seg}` → `dict` |
| `get_baseline(redis, video_id, seg_id)` | `HGETALL heatmap:{vid}:baseline:{seg}` → `dict` |
| `set_baseline(redis, video_id, seg_id, mean, stddev)` | `HSET heatmap:{vid}:baseline:{seg} mean M stddev S` |

**Test / Verify:**
```bash
cd services/heatmap-aggregator
python -c "
from app.heatmap.cache import record_event, get_total_counts, get_baseline, set_baseline
import inspect
for fn in [record_event, get_total_counts, get_baseline, set_baseline]:
    assert inspect.iscoroutinefunction(fn)
print('Heatmap cache OK')
"
```

**Acceptance criteria:**
- [ ] All 4 functions `async def`
- [ ] `record_event` increments BOTH live and total keys
- [ ] `record_event` sets correct TTLs (600 and 604800)
- [ ] After `HINCRBY`, publishes to `heatmap-updates:{video_id}` Redis pub/sub channel

---

### ✅ Task 20 — Write `app/heatmap/repository.py` (heatmap-aggregator)

**Functions:**

| Function | SQL |
|---|---|
| `insert_viewer_event(db, event_dict)` | `INSERT INTO viewer_events ...` |
| `bulk_insert_snapshots(db, video_id, segments)` | Batch `INSERT INTO video_heatmap_snapshots ...` |
| `insert_viral_alert(db, alert_dict)` | `INSERT INTO viral_segment_alerts ...` |
| `fetch_segment_stats(db)` | `SELECT video_id, segment_id, AVG(rewind_count), STDDEV(rewind_count) FROM ...` (for baseline) |
| `get_active_video_ids(redis)` | `SCAN heatmap:*:total:*` → extract distinct video IDs |

**Test / Verify:**
```bash
cd services/heatmap-aggregator
python -c "
from app.heatmap.repository import insert_viewer_event, bulk_insert_snapshots, insert_viral_alert
import inspect
for fn in [insert_viewer_event, bulk_insert_snapshots, insert_viral_alert]:
    assert inspect.iscoroutinefunction(fn)
print('Heatmap repository OK')
"
```

**Acceptance criteria:**
- [ ] All 5 functions `async def`, test exits 0

---

### ✅ Task 21 — Write `app/aggregator.py`

**File:** `services/heatmap-aggregator/app/aggregator.py`

**Functions:**

| Function | Logic |
|---|---|
| `get_segment_id(video_ts, segment_size)` | `int(video_ts // segment_size)` |
| `process_event(event, redis, db)` | Get `seg_id` → `cache.record_event()` → `repo.insert_viewer_event()` |

**Test / Verify:**
```bash
cd services/heatmap-aggregator
python -c "
from app.aggregator import get_segment_id
assert get_segment_id(0.0, 5) == 0
assert get_segment_id(4.9, 5) == 0
assert get_segment_id(5.0, 5) == 1
assert get_segment_id(142.5, 5) == 28
assert get_segment_id(144.9, 5) == 28
assert get_segment_id(145.0, 5) == 29
print('Segment bucketing OK — ts=142.5 → seg=28 ✅')
"
```

**Acceptance criteria:**
- [ ] `get_segment_id(142.5, 5)` returns `28` ✅
- [ ] All 6 boundary assertions pass
- [ ] Test exits 0

---

### ✅ Task 22 — Write `app/viral_detector.py`

**File:** `services/heatmap-aggregator/app/viral_detector.py`

**Function: `check_viral(redis, db, kafka_producer, video_id, seg_id)`**

**Logic:**
```python
async def check_viral(redis, db, kafka_producer, video_id: str, seg_id: int):
    counts = await cache.get_total_counts(redis, video_id, seg_id)
    rewind_count = int(counts.get("REWIND", 0))

    baseline = await cache.get_baseline(redis, video_id, seg_id)
    mean   = float(baseline.get("mean", 0))
    stddev = float(baseline.get("stddev", 1))  # avoid divide-by-zero

    sigma = (rewind_count - mean) / stddev
    if sigma > settings.viral_sigma_threshold:
        # Publish to Kafka heatmap-alerts
        await kafka_producer.publish("heatmap-alerts", video_id, {
            "videoId":   video_id,
            "segmentId": seg_id,
            "metric":    "REWIND_RATE",
            "value":     rewind_count,
            "sigma":     round(sigma, 2),
            "alertedAt": datetime.utcnow().isoformat()
        })
        # Persist to PostgreSQL
        await repo.insert_viral_alert(db, {...})
```

**Test / Verify:**
```bash
cd services/heatmap-aggregator
python -c "
from app.viral_detector import check_viral
import inspect
assert inspect.iscoroutinefunction(check_viral)
print('Viral detector signature OK')
"
```

**Acceptance criteria:**
- [ ] `check_viral` is `async def`
- [ ] Only fires when sigma > `viral_sigma_threshold` (default 3.0)
- [ ] Publishes to `heatmap-alerts` Kafka topic
- [ ] Writes to `viral_segment_alerts` DB table
- [ ] Test exits 0

---

### ✅ Task 23 — Write `app/flusher.py`

**File:** `services/heatmap-aggregator/app/flusher.py`

**Two async loop functions:**

| Function | Interval | Action |
|---|---|---|
| `hourly_flush(redis, db)` | 3600s | SCAN Redis for active videos → bulk insert snapshots |
| `weekly_baseline_recalc(redis, db)` | 604800s | Fetch `AVG`/`STDDEV` per segment from `viewer_events` → update `heatmap:{vid}:baseline:{seg}` in Redis |

**Test / Verify:**
```bash
cd services/heatmap-aggregator
python -c "
from app.flusher import hourly_flush, weekly_baseline_recalc
import inspect
for fn in [hourly_flush, weekly_baseline_recalc]:
    assert inspect.iscoroutinefunction(fn)
print('Flusher functions OK')
"
```

**Acceptance criteria:**
- [ ] Both functions `async def`
- [ ] `hourly_flush` resets live keys (not total) after snapshot
- [ ] Test exits 0

---

### ✅ Task 24 — Write `app/consumer.py` (heatmap-aggregator)

**Consumer group:** `heatmap-aggregator-group`
**Topic:** `viewer-interaction-events`

**Per-message logic:**
```
1. video_id = event["videoId"]
2. video_ts = event["videoTs"]
3. seg_id = get_segment_id(video_ts, settings.segment_size)
4. await cache.record_event(redis, video_id, seg_id, event["eventType"])
   └─ HINCRBY live key + total key + PUBLISH to heatmap-updates:{vid}
5. await repo.insert_viewer_event(db, event)
6. await check_viral(redis, db, kafka_producer, video_id, seg_id)
```

**Acceptance criteria:**
- [ ] Consumer group `heatmap-aggregator-group`
- [ ] All 3 steps happen in correct order per message
- [ ] Error on one message does NOT crash the consumer loop

---

### ✅ Task 25 — Write `app/main.py` (heatmap-aggregator)

```python
import asyncio
from app.consumer import consume
from app.flusher import hourly_flush, weekly_baseline_recalc

async def main():
    await connect_db()
    await connect_redis()
    await start_producer()
    await asyncio.gather(
        consume(),
        hourly_flush(redis_client, engine),
        weekly_baseline_recalc(redis_client, engine)
    )

if __name__ == "__main__":
    asyncio.run(main())
```

**Acceptance criteria:**
- [ ] Consumer + 2 background tasks run concurrently via `asyncio.gather`

---

### ✅ Task 26 — Add to `docker-compose.yml` (heatmap-aggregator)

```yaml
heatmap-aggregator:
  build: ./services/heatmap-aggregator
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    MONGO_USER: ${MONGO_USER}
    MONGO_PASSWORD: ${MONGO_PASSWORD}
    MONGO_HOST: ${MONGO_HOST}
    MONGO_PORT: ${MONGO_PORT}
    SEGMENT_SIZE: 5
  volumes:
    - ./services/shared:/app/shared:ro
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    kafka:
      condition: service_healthy
```

**Acceptance criteria:**
- [ ] No port mapping (consumer only)
- [ ] `SEGMENT_SIZE: 5` configured

---

### ✅ Task 27 — Write `tests/test_heatmap_aggregator.py` + Run

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_segment_bucketing_correct` | `ts=142.5, size=5` | `seg_id == 28` ✅ |
| `test_segment_bucketing_boundaries` | `ts=145.0` | `seg_id == 29` |
| `test_redis_incr_on_event` | Process REWIND event | `heatmap:{vid}:total:28 REWIND == 1` |
| `test_live_key_ttl` | After record_event | live key TTL ≤ 600 |
| `test_redis_pubsub_published` | record_event called | Redis PUBLISH called on `heatmap-updates:{vid}` |
| `test_viral_detection_publishes_alert` | sigma > 3.0 | Kafka `heatmap-alerts` published |
| `test_viral_detection_below_threshold` | sigma < 3.0 | No Kafka publish |
| `test_hourly_flush_writes_to_postgres` | `hourly_flush()` | `bulk_insert_snapshots` called |

**Run:**
```bash
cd services/heatmap-aggregator
pytest tests/test_heatmap_aggregator.py -v
```

**Acceptance criteria:**
- [ ] All 8 tests pass ✅
- [ ] Segment bucketing test explicitly verifies `ts=142.5 → seg=28`
- [ ] Redis operations use `fakeredis`

---

## 🟧 8c — Heatmap API

---

### ✅ Task 28 — Create Folder Structure (heatmap-api)

```bash
mkdir -p services/heatmap-api/app/heatmap \
         services/heatmap-api/tests
touch services/heatmap-api/app/__init__.py \
      services/heatmap-api/app/heatmap/__init__.py \
      services/heatmap-api/tests/__init__.py
```

**Acceptance criteria:**
- [ ] All dirs + `__init__.py` exist

---

### ✅ Task 29 — Write `requirements.txt` + `Dockerfile` (heatmap-api)

**`requirements.txt`:**
```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
aiokafka==0.10.0
redis[asyncio]==5.0.3
pydantic-settings==2.2.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
fakeredis==2.21.3
```

**`Dockerfile`:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
```

**Note:** No alembic (reads DB but owns no tables).

**Acceptance criteria:**
- [ ] Port `8007`, no alembic in CMD

---

### ✅ Task 30 — Write `app/config.py` (heatmap-api)

Same as event-ingestion config + `segment_size=5` + `summary_ttl=300`.

**Acceptance criteria:**
- [ ] `segment_size` and `summary_ttl` configurable, test exits 0

---

### ✅ Task 31 — Write `app/exceptions.py` (heatmap-api)

Re-export shared exceptions. Service uses `AuthError` (401) and `ForbiddenError` (403).

```python
from shared.exceptions import AppException, AuthError, ForbiddenError, NotFoundError
```

**Acceptance criteria:**
- [ ] Importable, test exits 0

---

### ✅ Task 32 — Write `app/heatmap/cache.py` (heatmap-api)

**What:** Read-only Redis access for heatmap data + summary key writer.

**Functions:**

| Function | Redis op |
|---|---|
| `get_all_segments(redis, video_id)` | SCAN `heatmap:{vid}:total:*` → HGETALL each |
| `get_live_segments(redis, video_id)` | SCAN `heatmap:{vid}:live:*` → HGETALL each |
| `update_summary(redis, video_id, segments)` | `HSET heatmap:{vid}:summary` + `EXPIRE 300` |

**Test / Verify:**
```bash
cd services/heatmap-api
python -c "
from app.heatmap.cache import get_all_segments, get_live_segments, update_summary
import inspect
for fn in [get_all_segments, get_live_segments, update_summary]:
    assert inspect.iscoroutinefunction(fn)
print('Heatmap API cache OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions `async def`, test exits 0

---

### ✅ Task 33 — Write `app/heatmap/repository.py` (heatmap-api)

**What:** DB fallback reads when Redis keys have expired.

**Functions:**

| Function | SQL |
|---|---|
| `get_snapshots(db, video_id)` | `SELECT * FROM video_heatmap_snapshots WHERE video_id=... ORDER BY snapshot_at DESC LIMIT 1 per segment` |
| `get_video_creator_id(db, video_id)` | `SELECT creator_id FROM videos WHERE id=...` — for auth check |

**Test / Verify:**
```bash
cd services/heatmap-api
python -c "
from app.heatmap.repository import get_snapshots, get_video_creator_id
import inspect
for fn in [get_snapshots, get_video_creator_id]:
    assert inspect.iscoroutinefunction(fn)
print('Heatmap API repository OK')
"
```

**Acceptance criteria:**
- [ ] Both functions `async def`, test exits 0

---

### ✅ Task 34 — Write `app/heatmap/service.py`

**Functions:**

| Function | Logic |
|---|---|
| `get_full_heatmap(db, redis, video_id, current_user_id)` | 1. Verify creator (403 if not). 2. `get_all_segments(redis, video_id)`. 3. If empty → DB fallback. 4. `update_summary(redis, video_id, segments)`. Return segments + hotSegment + coldSegment. |
| `get_live_heatmap(db, redis, video_id, current_user_id)` | Same auth check. Return live segments only. |
| `get_highlights(db, redis, video_id, current_user_id, top_n=5)` | Same auth check. Sort segments by REWIND count desc → return top 5 with rank + label. |

**Test / Verify:**
```bash
cd services/heatmap-api
python -c "
from app.heatmap.service import get_full_heatmap, get_live_heatmap, get_highlights
import inspect
for fn in [get_full_heatmap, get_live_heatmap, get_highlights]:
    assert inspect.iscoroutinefunction(fn)
print('Heatmap service OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions `async def`
- [ ] All 3 verify creator ownership (raise `ForbiddenError` if wrong user)
- [ ] `get_highlights` returns at most `top_n` (default 5) segments
- [ ] Test exits 0

---

### ✅ Task 35 — Write `app/heatmap/router.py`

**Endpoints:**

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/heatmap/{video_id}` | Required (creator only) | Full heatmap |
| `GET` | `/heatmap/{video_id}/live` | Required (creator only) | Live 5-min window |
| `GET` | `/heatmap/{video_id}/highlights` | Required (creator only) | Top 5 segments |
| `GET` | `/heatmap/{video_id}/stream` | Required | **SSE** `text/event-stream` |

**SSE implementation:**
```python
from fastapi.responses import StreamingResponse

@router.get("/{video_id}/stream")
async def stream_heatmap(video_id: str, request: Request, redis=Depends(get_redis), ...):
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

**Test / Verify:**
```bash
cd services/heatmap-api
python -c "
from app.heatmap.router import router
paths = {r.path for r in router.routes}
for p in ['/heatmap/{video_id}', '/heatmap/{video_id}/live',
          '/heatmap/{video_id}/highlights', '/heatmap/{video_id}/stream']:
    assert p in paths, f'Missing: {p}'
print('Heatmap API router OK')
"
```

**Acceptance criteria:**
- [ ] All 4 routes defined
- [ ] SSE route returns `text/event-stream`
- [ ] All routes require auth
- [ ] Test exits 0

---

### ✅ Task 36 — Write `app/consumer.py` (heatmap-api)

**Consumer group:** `heatmap-api-group`
**Topic:** `heatmap-aggregated`

**Logic:** Re-publish each message to Redis pub/sub so SSE generators receive it.

```python
await redis.publish(
    f"heatmap-updates:{event['videoId']}",
    json.dumps({"segId": event["segmentId"], "eventType": event["eventType"]})
)
```

**Acceptance criteria:**
- [ ] Consumer group `heatmap-api-group`
- [ ] Re-publishes to `heatmap-updates:{videoId}` Redis pub/sub

---

### ✅ Task 37 — Write `app/main.py` (heatmap-api)

**Lifespan startup:** `connect_db()` + `connect_redis()` + `asyncio.create_task(consume_aggregated())`
**Lifespan shutdown:** Cancel tasks + close resources

**Include router:**
```python
app.include_router(heatmap_router, prefix="/heatmap", tags=["heatmap"])
```

**Acceptance criteria:**
- [ ] All routes mounted, Kafka consumer background task started, test exits 0

---

### ✅ Task 38 — Add to `docker-compose.yml` (heatmap-api)

```yaml
heatmap-api:
  build: ./services/heatmap-api
  ports:
    - "8007:8007"
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    SEGMENT_SIZE: 5
  volumes:
    - ./services/shared:/app/shared:ro
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    kafka:
      condition: service_healthy
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0, `GET http://localhost:8007/docs` returns 200

---

### ✅ Task 39 — Write `tests/test_heatmap_api.py` + Run

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_get_heatmap_returns_segments` | Creator requests own video heatmap | 200, segments array with counts |
| `test_get_highlights_returns_top_5` | 10 segments in Redis | 200, exactly 5 highlights, sorted by REWIND desc |
| `test_get_heatmap_unauthenticated` | No cookie | 401 UNAUTHORIZED |
| `test_non_creator_returns_403` | Different user requests heatmap | 403 FORBIDDEN |
| `test_live_heatmap_returns_live_counts` | Live keys in Redis | 200, live segment data |

**Run:**
```bash
cd services/heatmap-api
pytest tests/test_heatmap_api.py -v
```

**Acceptance criteria:**
- [ ] All 5 tests pass ✅
- [ ] 403 test verifies creator-only access
- [ ] Highlights test verifies top-5 ordering

---

## Phase Complete Checklist

Before marking Phase 8 as ✅ done in `COPILOT.md`:

- [ ] All 39 tasks above are ✅ done
- [ ] All tests: 6 (event-ingestion) + 8 (aggregator) + 5 (heatmap-api) = **19 tests passing**
- [ ] Full end-to-end flow:
  - `POST /events/interaction {REWIND, ts:142.5}` → returns **202** in < 10ms
  - Redis key `heatmap:{vid}:total:28 REWIND` incremented ✅
  - `GET /heatmap/{vid}/highlights` shows segment 28 at top ✅
- [ ] SSE connection to `/heatmap/{vid}/stream` receives live updates
- [ ] `SEGMENT_SIZE=5` → `ts=142.5 → seg=28` verified in test
- [ ] Creator-only access enforced (403 for non-creators)
- [ ] Rate limit enforced (429 after 100 events/min)

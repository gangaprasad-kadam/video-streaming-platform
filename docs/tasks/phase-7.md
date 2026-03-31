# 📋 Phase 7 — Trending & Recommendations Task File

> **Goal:** FastAPI service (port 8005) that maintains a real-time trending leaderboard
> (Redis sorted set) and provides simple video recommendations (trending + watch history).
> Kafka consumer updates scores on every viewer interaction. Runs score decay hourly.

**Reference doc:** [`docs/phases/phase-7-trending-recommendations.md`](../phases/phase-7-trending-recommendations.md)
**Depends on:** Phase 1 ✅ (Kafka topics), Phase 3 ✅ (videos table), Phase 2 ✅ (users table)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure | ⬜ |
| 2 | Write `requirements.txt` | ⬜ |
| 3 | Write `Dockerfile` | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/database.py` | ⬜ |
| 6 | Write `app/redis_client.py` | ⬜ |
| 7 | Write `app/exceptions.py` | ⬜ |
| 8 | Write `app/models.py` (WatchHistory) | ⬜ |
| 9 | Set up Alembic + create `watch_history` migration | ⬜ |
| 10 | Write `app/consumer.py` | ⬜ |
| 11 | Write `app/trending/repository.py` + `cache.py` | ⬜ |
| 12 | Write `app/trending/service.py` | ⬜ |
| 13 | Write `app/trending/router.py` | ⬜ |
| 14 | Write `app/recommendations/repository.py` | ⬜ |
| 15 | Write `app/recommendations/service.py` | ⬜ |
| 16 | Write `app/recommendations/router.py` | ⬜ |
| 17 | Write `app/main.py` (with consumer + decay tasks) | ⬜ |
| 18 | Add to `docker-compose.yml` | ⬜ |
| 19 | Write `tests/test_trending.py` + run | ⬜ |
| 20 | Write `tests/test_recommendations.py` + run | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Create Folder Structure

```bash
mkdir -p services/trending-service/app/trending \
         services/trending-service/app/recommendations \
         services/trending-service/tests
touch services/trending-service/app/__init__.py \
      services/trending-service/app/trending/__init__.py \
      services/trending-service/app/recommendations/__init__.py \
      services/trending-service/tests/__init__.py
```

**Test / Verify:**
```bash
find services/trending-service -type f | sort
```

**Acceptance criteria:**
- [ ] `app/trending/`, `app/recommendations/`, `tests/` exist with `__init__.py`

---

### ✅ Task 2 — Write `requirements.txt`

**File:** `services/trending-service/requirements.txt`

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
aiokafka==0.10.0
redis[asyncio]==5.0.3
pydantic-settings==2.2.1
alembic==1.13.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
fakeredis==2.21.3
```

**Acceptance criteria:**
- [ ] All packages listed, `aiokafka` and `redis[asyncio]` included

---

### ✅ Task 3 — Write `Dockerfile`

**File:** `services/trending-service/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8005"]
```

**Acceptance criteria:**
- [ ] Alembic runs before uvicorn, port is `8005`

---

### ✅ Task 4 — Write `app/config.py`

**Settings:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_*` | 5 PG vars | — |
| `redis_host/port` | 2 Redis vars | — |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `trending_decay_factor` | `TRENDING_DECAY_FACTOR` | `0.9` |
| `trending_decay_interval` | `TRENDING_DECAY_INTERVAL` | `3600` |
| `trending_default_limit` | `TRENDING_DEFAULT_LIMIT` | `10` |

**Test / Verify:**
```bash
cd services/trending-service
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
python -c "
from app.config import settings
assert settings.trending_decay_factor == 0.9
assert settings.trending_decay_interval == 3600
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] Decay factor and interval configurable, test exits 0

---

### ✅ Task 5 — Write `app/database.py`

Same pattern as previous services.

**Expose:** `engine`, `AsyncSessionLocal`, `Base`, `connect_db()`, `close_db()`

**Test / Verify:**
```bash
cd services/trending-service
python -c "from app.database import connect_db; import inspect; assert inspect.iscoroutinefunction(connect_db); print('DB OK')"
```

**Acceptance criteria:**
- [ ] All 5 symbols importable, test exits 0

---

### ✅ Task 6 — Write `app/redis_client.py`

Same pattern as previous services.

**Expose:** `connect_redis()`, `close_redis()`, `get_redis()`, `redis_client` (module-level)

**Note:** Consumer directly uses `redis_client` (module-level instance set after `connect_redis()`).

**Test / Verify:**
```bash
cd services/trending-service
python -c "from app.redis_client import get_redis; import inspect; assert inspect.isasyncgenfunction(get_redis); print('Redis OK')"
```

**Acceptance criteria:**
- [ ] `get_redis` is async generator, module-level `redis_client` exported, test exits 0

---

### ✅ Task 7 — Write `app/exceptions.py`

Re-export shared exceptions only — no service-specific ones needed.

```python
from shared.exceptions import (
    AppException, NotFoundError, AuthError,
    ForbiddenError, ConflictError, RateLimitError
)
```

**Test / Verify:**
```bash
cd services/trending-service
python -c "from app.exceptions import AuthError; print('Exceptions OK')"
```

**Acceptance criteria:**
- [ ] Importable, test exits 0

---

### ✅ Task 8 — Write `app/models.py`

**File:** `services/trending-service/app/models.py`

**`WatchHistory` model columns:**

| Column | Type | Notes |
|---|---|---|
| `id` | `BigInteger` | PK, autoincrement |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` |
| `video_id` | `UUID` | NOT NULL, FK → `videos.id` |
| `watched_at` | `DateTime` | default `now()` |
| `watch_pct` | `Numeric(5,2)` | 0.00 – 100.00, nullable |
| **UNIQUE constraint** | `(user_id, video_id)` | Enables upsert on re-watch |

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.models import WatchHistory
cols = {c.name for c in WatchHistory.__table__.columns}
required = {'id', 'user_id', 'video_id', 'watched_at', 'watch_pct'}
assert required == cols, f'Missing: {required - cols}'
print('WatchHistory model OK')
"
```

**Acceptance criteria:**
- [ ] All 5 columns present
- [ ] UNIQUE constraint on `(user_id, video_id)`
- [ ] FK to both `users.id` and `videos.id`
- [ ] Test exits 0

---

### ✅ Task 9 — Set Up Alembic + Create Migration

```bash
cd services/trending-service
alembic init alembic
# Edit alembic.ini + env.py (same pattern as previous services)
alembic revision --autogenerate -m "create_watch_history_table"
```

**Test / Verify:**
```bash
alembic upgrade head
docker compose exec postgres psql -U admin -d videoplatform -c "\d watch_history"
```

**Acceptance criteria:**
- [ ] `alembic upgrade head` exits 0
- [ ] `watch_history` table has all 5 columns + UNIQUE constraint
- [ ] `idx_watch_history_user` index created

---

### ✅ Task 10 — Write `app/consumer.py`

**File:** `services/trending-service/app/consumer.py`

**Consumer group:** `trending-service-group`
**Topic:** `viewer-interaction-events`

**Score deltas:**
```python
SCORE_DELTAS = {
    "PLAY":    1.0,
    "PAUSE":   0.5,
    "REWIND":  3.0,
    "SEEK":    1.0,    # note: phase doc says 0.5 forward / 2 backward; use 1.0 as default
    "BUFFER": -0.5,
}
```

**Per-message logic:**
```
1. delta = SCORE_DELTAS.get(event["eventType"], 0)
2. If delta != 0:
     ZINCRBY trending:videos <delta> <event["videoId"]>
3. If event["eventType"] == "PLAY":
     UPSERT watch_history (user_id, video_id, watched_at)
     ON CONFLICT (user_id, video_id) DO UPDATE SET watched_at = NOW()
```

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.consumer import consume, SCORE_DELTAS
import inspect
assert inspect.iscoroutinefunction(consume)
assert SCORE_DELTAS['REWIND'] == 3.0
assert SCORE_DELTAS['BUFFER'] == -0.5
print('Consumer OK')
"
```

**Acceptance criteria:**
- [ ] `consume()` is `async def`
- [ ] `REWIND` increments by 3.0
- [ ] `BUFFER` decrements by 0.5
- [ ] `PLAY` events upsert `watch_history` table
- [ ] Unknown event types are skipped (delta = 0, no Redis write)
- [ ] Test exits 0

---

### ✅ Task 11 — Write Trending `repository.py` + `cache.py`

**`app/trending/repository.py`:**

| Function | SQL | Returns |
|---|---|---|
| `get_video_metadata(db, video_ids)` | `SELECT id, title, thumbnail_path, creator_id FROM videos WHERE id IN (...)` | `list[dict]` |

**`app/trending/cache.py`:**

| Function | Redis op | Notes |
|---|---|---|
| `get_trending_ids(redis, limit)` | `ZREVRANGE trending:videos 0 limit-1 WITHSCORES` | Returns `list[(video_id, score)]` |
| `increment_score(redis, video_id, delta)` | `ZINCRBY trending:videos delta video_id` | Used by consumer |
| `decay_all_scores(redis, factor)` | For each member: `ZADD trending:videos new_score video_id` | Hourly decay |

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.trending.repository import get_video_metadata
from app.trending.cache import get_trending_ids, increment_score, decay_all_scores
import inspect
for fn in [get_video_metadata, get_trending_ids, increment_score, decay_all_scores]:
    assert inspect.iscoroutinefunction(fn)
print('Trending repo + cache OK')
"
```

**Acceptance criteria:**
- [ ] All 4 functions `async def`
- [ ] `get_trending_ids` returns `(video_id, score)` tuples with scores
- [ ] `decay_all_scores` multiplies each score by `factor`
- [ ] Test exits 0

---

### ✅ Task 12 — Write `app/trending/service.py`

**File:** `services/trending-service/app/trending/service.py`

**Functions:**

| Function | Logic |
|---|---|
| `get_trending(db, redis, limit)` | 1. `get_trending_ids(redis, limit)` → list of `(video_id, score)`. 2. `get_video_metadata(db, video_ids)`. 3. Merge score into metadata. 4. Add `rank` field (1, 2, 3...). Return list. |

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.trending.service import get_trending
import inspect
assert inspect.iscoroutinefunction(get_trending)
print('Trending service OK')
"
```

**Acceptance criteria:**
- [ ] `get_trending` is `async def`
- [ ] Response includes `rank` field starting from 1
- [ ] Test exits 0

---

### ✅ Task 13 — Write `app/trending/router.py`

**File:** `services/trending-service/app/trending/router.py`

**Endpoint:**

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/trending` | None | 200, list of trending videos with rank + score |

**Query params:** `limit: int = 10` (max 100)

**Response schema:**
```python
class TrendingVideoResponse(BaseModel):
    video_id: str
    title: str
    thumbnail_path: str | None
    score: float
    rank: int
```

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.trending.router import router
paths = {r.path for r in router.routes}
assert '/trending' in paths
print('Trending router OK')
"
```

**Acceptance criteria:**
- [ ] Route `/trending` defined, no auth required
- [ ] `limit` query param with default 10
- [ ] Test exits 0

---

### ✅ Task 14 — Write Recommendations `repository.py`

**File:** `services/trending-service/app/recommendations/repository.py`

**Functions:**

| Function | SQL | Returns |
|---|---|---|
| `get_watch_history(db, user_id, limit)` | `SELECT video_id FROM watch_history WHERE user_id=... ORDER BY watched_at DESC LIMIT limit` | `list[str]` (video IDs) |
| `get_videos_by_creators(db, creator_ids, exclude_video_ids, limit)` | `SELECT id FROM videos WHERE creator_id IN (...) AND id NOT IN (...) ORDER BY created_at DESC LIMIT limit` | `list[str]` (video IDs) |
| `get_creator_ids_for_videos(db, video_ids)` | `SELECT DISTINCT creator_id FROM videos WHERE id IN (...)` | `list[str]` (creator IDs) |

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.recommendations.repository import get_watch_history, get_videos_by_creators, get_creator_ids_for_videos
import inspect
for fn in [get_watch_history, get_videos_by_creators, get_creator_ids_for_videos]:
    assert inspect.iscoroutinefunction(fn)
print('Recommendations repository OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions `async def`, test exits 0

---

### ✅ Task 15 — Write `app/recommendations/service.py`

**File:** `services/trending-service/app/recommendations/service.py`

**Function:** `get_recommendations(db, redis, user_id) → list[dict]`

**Algorithm:**
```
1. watched_ids  = await get_watch_history(db, user_id, limit=20)
2. trending_ids = [vid for vid, score in await get_trending_ids(redis, 20)]
3. unseen_trending = [v for v in trending_ids if v not in watched_ids]
4. creator_ids = await get_creator_ids_for_videos(db, watched_ids)
5. creator_vids = await get_videos_by_creators(db, creator_ids, exclude=watched_ids, limit=10)
6. results = unseen_trending[:6] + creator_vids[:4]
7. Return first 10, each annotated with reason: "trending" | "watch_history"
```

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.recommendations.service import get_recommendations
import inspect
assert inspect.iscoroutinefunction(get_recommendations)
print('Recommendations service OK')
"
```

**Acceptance criteria:**
- [ ] `get_recommendations` is `async def`
- [ ] Returns at most 10 items
- [ ] Each item has `reason` field: `"trending"` or `"watch_history"`
- [ ] Already-watched videos excluded from trending list
- [ ] Test exits 0

---

### ✅ Task 16 — Write `app/recommendations/router.py`

**File:** `services/trending-service/app/recommendations/router.py`

**Endpoint:**

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/recommendations` | Required (cookie) | 200, list of recommended videos |

**Response schema:**
```python
class RecommendationResponse(BaseModel):
    video_id: str
    title: str
    thumbnail_path: str | None
    reason: str  # "trending" | "watch_history"
```

**Uses:** `get_current_user` dependency

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.recommendations.router import router
paths = {r.path for r in router.routes}
assert '/recommendations' in paths
print('Recommendations router OK')
"
```

**Acceptance criteria:**
- [ ] Route `/recommendations` defined
- [ ] Auth required (session cookie)
- [ ] Returns 401 if not authenticated
- [ ] Test exits 0

---

### ✅ Task 17 — Write `app/main.py`

**File:** `services/trending-service/app/main.py`

**What:** FastAPI app with 3 background asyncio tasks + 3 exception handlers.

**Lifespan startup:**
1. `connect_db()`
2. `connect_redis()`
3. `asyncio.create_task(consume())` — Kafka consumer
4. `asyncio.create_task(decay_scores())` — hourly decay loop

**Decay loop:**
```python
async def decay_scores():
    while True:
        await asyncio.sleep(settings.trending_decay_interval)
        await cache.decay_all_scores(redis_client, settings.trending_decay_factor)
```

**Lifespan shutdown:**
1. Cancel all created tasks
2. `close_redis()` + `close_db()`

**Include routers:**
```python
app.include_router(trending_router, prefix="/trending", tags=["trending"])
app.include_router(recommendations_router, prefix="/recommendations", tags=["recommendations"])
```

**Test / Verify:**
```bash
cd services/trending-service
python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/trending' in paths
assert '/recommendations' in paths
print('main.py OK')
"
```

**Acceptance criteria:**
- [ ] Kafka consumer started as background task
- [ ] Decay loop started as background task
- [ ] Both routers mounted
- [ ] All 3 exception handlers registered
- [ ] Test exits 0

---

### ✅ Task 18 — Add to `docker-compose.yml`

```yaml
trending-service:
  build: ./services/trending-service
  ports:
    - "8005:8005"
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    TRENDING_DECAY_FACTOR: 0.9
    TRENDING_DECAY_INTERVAL: 3600
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

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build trending-service
docker compose up -d trending-service
sleep 5
curl -f http://localhost:8005/docs
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] `GET http://localhost:8005/docs` returns 200
- [ ] Service starts without crash

---

### ✅ Task 19 — Write `tests/test_trending.py` + Run

**File:** `services/trending-service/tests/test_trending.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_get_trending_empty` | No scores in Redis | 200, empty list |
| `test_get_trending_with_scores` | 5 videos with scores | 200, ordered by score desc, rank 1–5 |
| `test_score_incremented_on_play` | Consumer receives PLAY event | `ZINCRBY trending:videos 1.0 videoId` called |
| `test_score_incremented_on_rewind` | Consumer receives REWIND event | `ZINCRBY trending:videos 3.0 videoId` called |
| `test_buffer_decrements_score` | Consumer receives BUFFER event | Score decreased by 0.5 |
| `test_decay_reduces_scores` | `decay_all_scores(redis, 0.9)` | Each score × 0.9 |
| `test_play_upserts_watch_history` | PLAY event in consumer | `watch_history` row created/updated |

**Run:**
```bash
cd services/trending-service
pytest tests/test_trending.py -v
```

**Acceptance criteria:**
- [ ] All 7 tests pass ✅
- [ ] Redis operations mocked with `fakeredis`
- [ ] Decay test verifies `score * 0.9` for each member
- [ ] `pytest -v` exits 0

---

### ✅ Task 20 — Write `tests/test_recommendations.py` + Run

**File:** `services/trending-service/tests/test_recommendations.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_recommendations_excludes_watched` | User watched video A; A is trending | A not in recommendations |
| `test_recommendations_includes_trending` | Unwatched videos B,C trending | B,C appear with `reason=trending` |
| `test_recommendations_includes_creator_videos` | User watched vid by creator X | Other vids by X appear with `reason=watch_history` |
| `test_recommendations_requires_auth` | No session cookie | 401 UNAUTHORIZED |
| `test_recommendations_max_10` | 20 trending + 20 creator vids | Returns exactly 10 |

**Run:**
```bash
cd services/trending-service
pytest tests/test_recommendations.py -v
```

**Acceptance criteria:**
- [ ] All 5 tests pass ✅
- [ ] Watched video exclusion test passes
- [ ] Max 10 results enforced
- [ ] `pytest -v` exits 0

---

### ✅ Final: Run Full Test Suite

```bash
cd services/trending-service
pytest tests/ -v --tb=short
```

**Acceptance criteria:**
- [ ] All 12 tests passing (7 trending + 5 recommendations), 0 failing

---

## Phase Complete Checklist

Before marking Phase 7 as ✅ done in `COPILOT.md`:

- [ ] All 20 tasks above are ✅ done
- [ ] All 12 tests passing, 0 failing
- [ ] `GET http://localhost:8005/trending` returns scored + ranked list
- [ ] `GET http://localhost:8005/recommendations` returns 10 items with `reason` field
- [ ] Redis `trending:videos` sorted set populated after viewer events
- [ ] `watch_history` table upserted on `PLAY` events
- [ ] Score decay task running (confirmed in logs)
- [ ] Kafka consumer group `trending-service-group` active

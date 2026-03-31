# 📋 Phase 1 — Infrastructure & Skeleton Task File

> **Goal:** Bring up all shared infrastructure. After this phase, `docker-compose up` starts
> PostgreSQL, MongoDB, Redis, Kafka, and NGINX — all healthy and reachable — and the
> shared Python module is ready for every service to use.

**Reference doc:** [`docs/phases/phase-1-infrastructure.md`](../phases/phase-1-infrastructure.md)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Create project folder structure | ⬜ |
| 2 | Create `.env.example` | ⬜ |
| 3 | Write `docker-compose.yml` — infra services | ⬜ |
| 4 | Add `kafka-setup` init container to docker-compose | ⬜ |
| 5 | Write `nginx/nginx.conf` | ⬜ |
| 6 | Write `services/shared/__init__.py` | ⬜ |
| 7 | Write `services/shared/exceptions.py` | ⬜ |
| 8 | Write `services/shared/schemas.py` | ⬜ |
| 9 | Write `services/shared/dependencies.py` | ⬜ |
| 10 | Verify infra containers start healthy | ⬜ |
| 11 | Verify Kafka topics are created | ⬜ |
| 12 | Verify shared module is importable | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Create Project Folder Structure

**What:** Create all directories and placeholder files so the repo has the correct shape.

**Files to create:**
```
project/
├── nginx/                         ← empty dir, populated in Task 5
├── services/
│   └── shared/                    ← populated in Tasks 6-9
├── frontend/                      ← empty, populated in Phase 9
└── docs/
    └── tasks/                     ← this file lives here
```

**Commands:**
```bash
mkdir -p nginx services/shared frontend docs/tasks
touch services/shared/__init__.py
```

**Test / Verify:**
```bash
find . -not -path './.git/*' -type d | sort
```

**Acceptance criteria:**
- [ ] Directories `nginx/`, `services/shared/`, `frontend/` exist
- [ ] `services/shared/__init__.py` exists (even if empty)

---

### ✅ Task 2 — Create `.env.example`

**What:** Commit a safe environment variable template (no real secrets).

**File:** `.env.example` at project root

**Content:**
```env
# PostgreSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=videoplatform
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# MongoDB
MONGO_USER=admin
MONGO_PASSWORD=secret
MONGO_HOST=mongodb
MONGO_PORT=27017

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Session
SESSION_SECRET=change_me_in_production
SESSION_TTL_SECONDS=86400

# AI (used in Phase 6)
WHISPER_MODEL=base
HF_MODEL=facebook/bart-large-cnn

# Heatmap
SEGMENT_SIZE=5

# Service ports
USER_SERVICE_PORT=8001
VIDEO_SERVICE_PORT=8002
STREAMING_SERVICE_PORT=8003
SUMMARIZATION_SERVICE_PORT=8004
TRENDING_SERVICE_PORT=8005
EVENT_INGESTION_PORT=8006
HEATMAP_API_PORT=8007
```

**Also create `.env` from template (gitignored):**
```bash
cp .env.example .env
```

**Test / Verify:**
```bash
cat .env.example | grep -c "="   # should print >= 15
grep ".env" .gitignore            # confirm .env is gitignored
```

**Acceptance criteria:**
- [ ] `.env.example` exists and has all variables listed above
- [ ] `.env` is listed in `.gitignore`

---

### ✅ Task 3 — Write `docker-compose.yml` — Infra Services

**What:** Define the 6 infra containers: postgres, mongodb, redis, zookeeper, kafka, nginx.
All should have healthchecks. Volumes should be named.

**File:** `docker-compose.yml` at project root

**Services to define:**

| Service | Image | Port | Healthcheck |
|---|---|---|---|
| `postgres` | `postgres:15` | 5432 | `pg_isready -U ${POSTGRES_USER}` |
| `mongodb` | `mongo:6` | 27017 | none (optional) |
| `redis` | `redis:7-alpine` | 6379 | `redis-cli ping` |
| `zookeeper` | `confluentinc/cp-zookeeper:7.5.0` | 2181 | none |
| `kafka` | `confluentinc/cp-kafka:7.5.0` | 9092 | `kafka-broker-api-versions --bootstrap-server kafka:9092` |
| `nginx` | `nginx:alpine` | 80 | none |

**Named volumes required:** `postgres_data`, `mongo_data`

**Test / Verify:**
```bash
docker compose config --quiet     # validates YAML + env substitution
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0 with no errors
- [ ] All 6 services defined with correct images and ports
- [ ] postgres and redis have healthchecks
- [ ] kafka has healthcheck
- [ ] Named volumes `postgres_data` and `mongo_data` declared

---

### ✅ Task 4 — Add `kafka-setup` Init Container

**What:** Add a one-shot init container that creates all 5 Kafka topics after Kafka is healthy.

**Add to `docker-compose.yml`:**

| Topic | Partitions |
|---|---|
| `video.uploaded` | 3 |
| `video.processed` | 3 |
| `viewer-interaction-events` | 12 |
| `heatmap-aggregated` | 6 |
| `heatmap-alerts` | 3 |

**Container spec:**
```yaml
kafka-setup:
  image: confluentinc/cp-kafka:7.5.0
  depends_on:
    kafka:
      condition: service_healthy
  restart: on-failure
```

**Test / Verify (after `docker compose up -d`):**
```bash
docker compose exec kafka \
  kafka-topics --bootstrap-server kafka:9092 --list
# Expected output includes all 5 topics
```

**Acceptance criteria:**
- [ ] All 5 topics appear in `kafka-topics --list`
- [ ] `kafka-setup` container exits 0 (not restarting)

---

### ✅ Task 5 — Write `nginx/nginx.conf`

**What:** Configure NGINX as API gateway routing to all 7 microservices + frontend.

**File:** `nginx/nginx.conf`

**Routes to configure:**

| Location prefix | Upstream |
|---|---|
| `/auth/` | `user-service:8001` |
| `/users/` | `user-service:8001` |
| `/videos/` | `video-service:8002` |
| `/stream/` | `streaming-service:8003` |
| `/summary/` | `summarization-service:8004` |
| `/trending/` | `trending-service:8005` |
| `/recommendations/` | `trending-service:8005` |
| `/events/` | `event-ingestion:8006` |
| `/heatmap/` | `heatmap-api:8007` |
| `/` | `frontend:3000` |

**Test / Verify (after `docker compose up -d`):**
```bash
docker compose exec nginx nginx -t
# Output: "syntax is ok" + "test is successful"
```

**Acceptance criteria:**
- [ ] `nginx -t` passes with no errors
- [ ] All 7 upstream service blocks defined
- [ ] All location blocks defined with correct proxy_pass

---

### ✅ Task 6 — Write `services/shared/__init__.py`

**What:** Makes `shared` a Python package and re-exports the key symbols.

**File:** `services/shared/__init__.py`

**Content:**
```python
from .exceptions import AppException, NotFoundError, AuthError, ForbiddenError, ConflictError, RateLimitError
from .schemas import SuccessResponse, ErrorResponse, PagedResponse
```

**Test / Verify:**
```bash
cd services && python -c "import shared; print('OK')"
```

**Acceptance criteria:**
- [ ] File exists and does not throw on import

---

### ✅ Task 7 — Write `services/shared/exceptions.py`

**What:** Define the standard exception hierarchy used by every service.

**File:** `services/shared/exceptions.py`

**Exceptions to define:**

| Class | HTTP Status | Error Code |
|---|---|---|
| `AppException` (base) | configurable | configurable |
| `NotFoundError` | 404 | `{resource}_NOT_FOUND` |
| `AuthError` | 401 | `UNAUTHORIZED` |
| `ForbiddenError` | 403 | `FORBIDDEN` |
| `ConflictError` | 409 | `CONFLICT` |
| `RateLimitError` | 429 | `RATE_LIMIT_EXCEEDED` |

**Test / Verify:**
```bash
cd services && python -c "
from shared.exceptions import NotFoundError, AuthError, ForbiddenError, ConflictError, RateLimitError
e = NotFoundError('video')
assert e.status_code == 404
assert 'NOT_FOUND' in e.error_code
print('All exceptions OK')
"
```

**Acceptance criteria:**
- [ ] All 6 exception classes importable
- [ ] Each has `status_code`, `error_code`, `message` attributes
- [ ] `NotFoundError('video')` produces `error_code = 'VIDEO_NOT_FOUND'`
- [ ] Test command above exits 0

---

### ✅ Task 8 — Write `services/shared/schemas.py`

**What:** Define the standard response envelopes used by every endpoint.

**File:** `services/shared/schemas.py`

**Schemas to define (Pydantic v2):**

```python
# Success response
SuccessResponse[T]:  { data: T, message: str = "success" }

# Error response
ErrorResponse:  { error: str, message: str, detail: Any = None }

# Paginated response
PagedResponse[T]:  { data: list[T], total: int, page: int, page_size: int }
```

**Test / Verify:**
```bash
cd services && python -c "
from shared.schemas import SuccessResponse, ErrorResponse, PagedResponse
r = SuccessResponse[dict](data={'id': 1})
assert r.message == 'success'
e = ErrorResponse(error='NOT_FOUND', message='Video not found')
assert e.detail is None
print('All schemas OK')
"
```

**Acceptance criteria:**
- [ ] All 3 generics importable
- [ ] `SuccessResponse` defaults `message` to `"success"`
- [ ] `ErrorResponse` defaults `detail` to `None`
- [ ] Test command exits 0

---

### ✅ Task 9 — Write `services/shared/dependencies.py`

**What:** FastAPI dependency functions shared by every protected service.

**File:** `services/shared/dependencies.py`

**Functions to define:**

| Function | Returns | Raises |
|---|---|---|
| `get_db()` | `AsyncSession` (SQLAlchemy) | — |
| `get_redis()` | `Redis` (aioredis) | — |
| `get_current_user(request, redis)` | `user_id: str` | `AuthError` if no/expired session |

**Session auth logic for `get_current_user`:**
1. Read `session_id` cookie from request
2. If missing → raise `AuthError`
3. `user_id = await redis.get(f"session:{session_id}")`
4. If `None` → raise `AuthError` (expired or invalid)
5. Refresh TTL: `await redis.expire(f"session:{session_id}", SESSION_TTL_SECONDS)`
6. Return `user_id`

**Test / Verify:**
```bash
cd services && python -c "
from shared.dependencies import get_db, get_redis, get_current_user
import inspect
assert inspect.isasyncgenfunction(get_db)
assert inspect.isasyncgenfunction(get_redis)
assert inspect.iscoroutinefunction(get_current_user)
print('Dependencies signature OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions importable
- [ ] `get_db` and `get_redis` are async generators (for FastAPI `Depends`)
- [ ] `get_current_user` reads `session_id` cookie and looks up Redis
- [ ] Test command exits 0

---

### ✅ Task 10 — Verify Infra Containers Start Healthy

**What:** Run `docker compose up -d` and confirm all containers reach healthy/running state.

**Commands:**
```bash
docker compose up -d
sleep 30   # give Kafka time to start
docker compose ps
```

**Expected output:** Every service shows `healthy` or `running`. Nothing shows `Exit` or `Restarting`.

**Test / Verify:**
```bash
# PostgreSQL
docker compose exec postgres pg_isready -U admin
# → /var/run/postgresql:5432 - accepting connections

# Redis
docker compose exec redis redis-cli ping
# → PONG

# MongoDB
docker compose exec mongodb mongosh --eval "db.runCommand({ping:1})" --quiet
# → { ok: 1 }

# Kafka broker
docker compose exec kafka kafka-broker-api-versions \
  --bootstrap-server kafka:9092 > /dev/null && echo "Kafka OK"
```

**Acceptance criteria:**
- [ ] All 6 infra containers in `docker compose ps` show no `Exit` state
- [ ] `pg_isready` returns accepting connections
- [ ] `redis-cli ping` returns `PONG`
- [ ] MongoDB ping returns `{ ok: 1 }`
- [ ] Kafka broker API versions call succeeds

---

### ✅ Task 11 — Verify Kafka Topics Are Created

**What:** Confirm all 5 pre-created topics exist and have the correct partition counts.

**Commands:**
```bash
docker compose exec kafka \
  kafka-topics --bootstrap-server kafka:9092 --list
```

**Test / Verify:**
```bash
docker compose exec kafka \
  kafka-topics --bootstrap-server kafka:9092 --describe \
  --topic video.uploaded,video.processed,viewer-interaction-events,heatmap-aggregated,heatmap-alerts
```

**Expected:** Each topic described with correct partition count.

**Acceptance criteria:**
- [ ] `video.uploaded` — 3 partitions
- [ ] `video.processed` — 3 partitions
- [ ] `viewer-interaction-events` — 12 partitions
- [ ] `heatmap-aggregated` — 6 partitions
- [ ] `heatmap-alerts` — 3 partitions

---

### ✅ Task 12 — Verify Shared Module is Importable

**What:** Confirm the shared Python package works correctly end-to-end before any service depends on it.

**Commands:**
```bash
cd services
python -c "
from shared.exceptions import NotFoundError, AuthError, ForbiddenError, ConflictError, RateLimitError
from shared.schemas import SuccessResponse, ErrorResponse, PagedResponse
from shared.dependencies import get_db, get_redis, get_current_user

# Smoke test exceptions
e = NotFoundError('video')
assert e.status_code == 404, f'Expected 404, got {e.status_code}'

e2 = AuthError()
assert e2.status_code == 401, f'Expected 401, got {e2.status_code}'

# Smoke test schemas
r = SuccessResponse[dict](data={'ok': True})
assert r.message == 'success'

print('✅ Shared module fully verified')
"
```

**Acceptance criteria:**
- [ ] Script exits 0 with `✅ Shared module fully verified`
- [ ] No import errors
- [ ] No assertion errors

---

## Phase Complete Checklist

Before marking Phase 1 as ✅ done in `COPILOT.md`:

- [ ] All 12 tasks above are ✅ done
- [ ] `docker compose ps` — all containers healthy/running
- [ ] All 5 Kafka topics exist with correct partitions
- [ ] `services/shared/` module passes full smoke test
- [ ] `.env.example` committed, `.env` gitignored
- [ ] `nginx -t` passes

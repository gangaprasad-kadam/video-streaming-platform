# 📋 Phase 2 — User Service Task File

> **Goal:** A standalone FastAPI microservice on port 8001 that handles user registration,
> login, logout, and profile retrieval. Uses bcrypt for passwords and Redis for sessions.

**Reference doc:** [`docs/phases/phase-2-user-service.md`](../phases/phase-2-user-service.md)
**Depends on:** Phase 1 complete ✅
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure for user-service | ⬜ |
| 2 | Write `requirements.txt` | ⬜ |
| 3 | Write `Dockerfile` | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/database.py` | ⬜ |
| 6 | Write `app/redis_client.py` | ⬜ |
| 7 | Write `app/models.py` (SQLAlchemy User model) | ⬜ |
| 8 | Set up Alembic + create `users` table migration | ⬜ |
| 9 | Write `app/exceptions.py` and `app/dependencies.py` | ⬜ |
| 10 | Write `app/auth/schemas.py` | ⬜ |
| 11 | Write `app/auth/repository.py` | ⬜ |
| 12 | Write `app/auth/cache.py` | ⬜ |
| 13 | Write `app/auth/service.py` | ⬜ |
| 14 | Write `app/auth/router.py` | ⬜ |
| 15 | Write `app/users/schemas.py` + `repository.py` + `service.py` | ⬜ |
| 16 | Write `app/users/router.py` | ⬜ |
| 17 | Write `app/main.py` | ⬜ |
| 18 | Add `user-service` to `docker-compose.yml` | ⬜ |
| 19 | Write `tests/conftest.py` | ⬜ |
| 20 | Write `tests/test_auth.py` + run | ⬜ |
| 21 | Write `tests/test_users.py` + run | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Create Folder Structure

**What:** Create all directories and empty `__init__.py` files.

**Target structure:**
```
services/user-service/
├── app/
│   ├── auth/
│   └── users/
└── tests/
```

**Commands:**
```bash
mkdir -p services/user-service/app/auth \
         services/user-service/app/users \
         services/user-service/tests
touch services/user-service/app/__init__.py \
      services/user-service/app/auth/__init__.py \
      services/user-service/app/users/__init__.py \
      services/user-service/tests/__init__.py
```

**Test / Verify:**
```bash
find services/user-service -type f | sort
```

**Acceptance criteria:**
- [ ] All directories and `__init__.py` files exist

---

### ✅ Task 2 — Write `requirements.txt`

**File:** `services/user-service/requirements.txt`

**Content:**
```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
redis[asyncio]==5.0.3
bcrypt==4.1.2
pydantic-settings==2.2.1
pydantic[email]==2.6.4
alembic==1.13.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
```

**Test / Verify:**
```bash
pip install -r services/user-service/requirements.txt --dry-run 2>&1 | tail -5
# should show "Would install ..." without errors
```

**Acceptance criteria:**
- [ ] File exists with all packages listed
- [ ] No dependency conflicts (dry-run passes)

---

### ✅ Task 3 — Write `Dockerfile`

**File:** `services/user-service/Dockerfile`

**Rules:**
- Base: `python:3.11-slim`
- Run Alembic migrations before uvicorn starts
- Port: `8001`
- Shared module mounted at runtime (not COPYed)

**Content:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
```

**Test / Verify:**
```bash
docker build -t user-service-test services/user-service/
# should exit 0 (build succeeds — note: alembic.ini not yet created, do after Task 8)
```

**Acceptance criteria:**
- [ ] Dockerfile exists
- [ ] CMD runs `alembic upgrade head` before `uvicorn`

---

### ✅ Task 4 — Write `app/config.py`

**File:** `services/user-service/app/config.py`

**What:** Pydantic `BaseSettings` that reads env vars. Provides a `POSTGRES_URL` property.

**Settings to expose:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_user` | `POSTGRES_USER` | — |
| `postgres_password` | `POSTGRES_PASSWORD` | — |
| `postgres_db` | `POSTGRES_DB` | — |
| `postgres_host` | `POSTGRES_HOST` | `postgres` |
| `postgres_port` | `POSTGRES_PORT` | `5432` |
| `redis_host` | `REDIS_HOST` | `redis` |
| `redis_port` | `REDIS_PORT` | `6379` |
| `session_ttl_seconds` | `SESSION_TTL_SECONDS` | `86400` |

**`POSTGRES_URL` property:** `postgresql+asyncpg://{user}:{pass}@{host}:{port}/{db}`

**Test / Verify:**
```bash
cd services/user-service
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
python -c "
from app.config import settings
assert 'asyncpg' in settings.POSTGRES_URL
assert settings.session_ttl_seconds == 86400
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] All env vars mapped
- [ ] `POSTGRES_URL` property returns async-compatible URL
- [ ] Test command exits 0

---

### ✅ Task 5 — Write `app/database.py`

**File:** `services/user-service/app/database.py`

**What:** SQLAlchemy async engine + session factory + `get_db` dependency.

**Key objects to expose:**
- `engine` — `create_async_engine(settings.POSTGRES_URL)`
- `AsyncSessionLocal` — `async_sessionmaker(engine, expire_on_commit=False)`
- `Base` — `DeclarativeBase` for models
- `connect_db()` / `close_db()` — lifecycle functions called by `main.py` lifespan

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.database import Base, AsyncSessionLocal, connect_db, close_db
import inspect
assert inspect.iscoroutinefunction(connect_db)
assert inspect.iscoroutinefunction(close_db)
print('Database module OK')
"
```

**Acceptance criteria:**
- [ ] `Base`, `AsyncSessionLocal`, `connect_db`, `close_db` importable
- [ ] `connect_db` and `close_db` are async functions
- [ ] Test command exits 0

---

### ✅ Task 6 — Write `app/redis_client.py`

**File:** `services/user-service/app/redis_client.py`

**What:** Redis connection lifecycle + `get_redis` FastAPI dependency.

**Expose:**
- `redis_client` (module-level, set during lifespan)
- `connect_redis()` / `close_redis()` — lifecycle functions
- `get_redis()` — async generator for FastAPI `Depends`

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.redis_client import get_redis, connect_redis, close_redis
import inspect
assert inspect.isasyncgenfunction(get_redis)
print('Redis client module OK')
"
```

**Acceptance criteria:**
- [ ] `get_redis` is async generator
- [ ] `connect_redis` / `close_redis` are async functions
- [ ] Test command exits 0

---

### ✅ Task 7 — Write `app/models.py`

**File:** `services/user-service/app/models.py`

**What:** SQLAlchemy ORM model for the `users` table.

**Columns:**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` |
| `username` | `String(50)` | UNIQUE, NOT NULL |
| `email` | `String(255)` | UNIQUE, NOT NULL |
| `password_hash` | `String(60)` | NOT NULL |
| `created_at` | `DateTime` | default `now()` |
| `updated_at` | `DateTime` | default `now()`, onupdate |

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.models import User
cols = {c.name for c in User.__table__.columns}
required = {'id', 'username', 'email', 'password_hash', 'created_at', 'updated_at'}
assert required == cols, f'Missing: {required - cols}'
print('User model OK')
"
```

**Acceptance criteria:**
- [ ] `User` model importable from `app.models`
- [ ] All 6 columns present
- [ ] `email` and `username` have `unique=True`
- [ ] Test command exits 0

---

### ✅ Task 8 — Set Up Alembic + Create Migration

**What:** Initialize Alembic and create the first migration that creates the `users` table.

**Steps:**
```bash
cd services/user-service
alembic init alembic
# Then edit alembic.ini + alembic/env.py to use async engine from app.config
```

**Edit `alembic/env.py` to:**
1. Import `settings` from `app.config`
2. Set `config.set_main_option("sqlalchemy.url", settings.POSTGRES_URL)`
3. Import `Base` from `app.database` for `target_metadata`
4. Use `run_async_migrations()` for async engine support

**Generate migration:**
```bash
alembic revision --autogenerate -m "create_users_table"
```

**Test / Verify (requires running postgres):**
```bash
alembic upgrade head
# then check table exists:
docker compose exec postgres psql -U admin -d videoplatform \
  -c "\d users"
```

**Acceptance criteria:**
- [ ] `alembic.ini` exists
- [ ] `alembic/versions/` has at least 1 migration file
- [ ] `alembic upgrade head` exits 0
- [ ] `\d users` shows all 6 columns with correct types

---

### ✅ Task 9 — Write `app/exceptions.py` and `app/dependencies.py`

**What:** Thin re-export files so service code imports from `app.*` not `shared.*`.

**`app/exceptions.py`:**
```python
from shared.exceptions import (
    AppException, NotFoundError, AuthError,
    ForbiddenError, ConflictError, RateLimitError
)
__all__ = ["AppException", "NotFoundError", "AuthError",
           "ForbiddenError", "ConflictError", "RateLimitError"]
```

**`app/dependencies.py`:**
```python
from shared.dependencies import get_db, get_redis, get_current_user
__all__ = ["get_db", "get_redis", "get_current_user"]
```

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.exceptions import AuthError, ConflictError
from app.dependencies import get_current_user
print('Re-exports OK')
"
```

**Acceptance criteria:**
- [ ] Both files importable without errors
- [ ] Test command exits 0

---

### ✅ Task 10 — Write `app/auth/schemas.py`

**File:** `services/user-service/app/auth/schemas.py`

**Schemas:**

| Schema | Fields | Validators |
|---|---|---|
| `RegisterRequest` | `username` (3–50), `email` (EmailStr), `password` (8–72) | — |
| `LoginRequest` | `email` (EmailStr), `password` (8–72) | — |
| `UserResponse` | `id`, `username`, `email`, `created_at` | `model_config = ConfigDict(from_attributes=True)` |

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.auth.schemas import RegisterRequest, LoginRequest, UserResponse
from pydantic import ValidationError
try:
    RegisterRequest(username='ab', email='x@y.com', password='short')
    assert False, 'Should have raised'
except ValidationError:
    pass
r = RegisterRequest(username='alice', email='alice@example.com', password='securepass')
assert r.username == 'alice'
print('Auth schemas OK')
"
```

**Acceptance criteria:**
- [ ] `username` min_length=3 enforced
- [ ] `password` min_length=8 enforced
- [ ] `email` validates as email format
- [ ] `UserResponse` has `from_attributes=True`
- [ ] Test command exits 0

---

### ✅ Task 11 — Write `app/auth/repository.py`

**File:** `services/user-service/app/auth/repository.py`

**What:** Pure DB query functions — no business logic.

**Functions:**

| Function | SQL | Returns |
|---|---|---|
| `create_user(db, username, email, password_hash)` | `INSERT INTO users ...` | `User` ORM object |
| `get_user_by_email(db, email)` | `SELECT ... WHERE email=...` | `User \| None` |
| `get_user_by_id(db, user_id)` | `SELECT ... WHERE id=...` | `User \| None` |

**Rules:**
- Only `async def` functions
- Only SQLAlchemy queries — no business logic
- Raise nothing — return None on not found

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.auth.repository import create_user, get_user_by_email, get_user_by_id
import inspect
for fn in [create_user, get_user_by_email, get_user_by_id]:
    assert inspect.iscoroutinefunction(fn), f'{fn.__name__} must be async'
print('Auth repository signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions are `async def`
- [ ] No business logic (no hashing, no session creation)
- [ ] Test command exits 0

---

### ✅ Task 12 — Write `app/auth/cache.py`

**File:** `services/user-service/app/auth/cache.py`

**What:** Redis session operations only.

**Functions:**

| Function | Redis op | Notes |
|---|---|---|
| `create_session(redis, user_id)` | `SET session:{sid} user_id EX 86400` | Returns `session_id` (new UUID) |
| `delete_session(redis, session_id)` | `DEL session:{sid}` | — |
| `get_user_id_from_session(redis, session_id)` | `GET session:{sid}` | Returns `str \| None` |

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.auth.cache import create_session, delete_session, get_user_id_from_session
import inspect
for fn in [create_session, delete_session, get_user_id_from_session]:
    assert inspect.iscoroutinefunction(fn), f'{fn.__name__} must be async'
print('Auth cache signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions are `async def`
- [ ] `create_session` generates a UUID and returns it
- [ ] Uses `session:` prefix for all Redis keys
- [ ] Test command exits 0

---

### ✅ Task 13 — Write `app/auth/service.py`

**File:** `services/user-service/app/auth/service.py`

**What:** All business logic. Calls repository + cache. No HTTP/Pydantic here.

**Functions:**

| Function | Logic |
|---|---|
| `register(db, data: RegisterRequest)` | Check duplicate email → raise `ConflictError` if exists → hash password → `create_user` → return `User` |
| `login(db, redis, data: LoginRequest)` | Fetch user by email → raise `AuthError` if not found → verify password → raise `AuthError` if wrong → `create_session` → return `(User, session_id)` |
| `logout(redis, session_id)` | `delete_session(redis, session_id)` |

**Password hashing:**
```python
import bcrypt
def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.auth.service import register, login, logout
import inspect
for fn in [register, login, logout]:
    assert inspect.iscoroutinefunction(fn), f'{fn.__name__} must be async'
print('Auth service signatures OK')
"
```

**Acceptance criteria:**
- [ ] `register` raises `ConflictError` on duplicate email
- [ ] `login` raises `AuthError` on wrong password or unknown email
- [ ] All functions `async def`
- [ ] No raw SQL — only calls to repository/cache
- [ ] Test command exits 0

---

### ✅ Task 14 — Write `app/auth/router.py`

**File:** `services/user-service/app/auth/router.py`

**Endpoints:**

| Method | Path | Auth required | Success | Error |
|---|---|---|---|---|
| `POST` | `/auth/register` | No | 201 + `UserResponse` | 409 CONFLICT |
| `POST` | `/auth/login` | No | 200 + set cookie | 401 UNAUTHORIZED |
| `POST` | `/auth/logout` | Yes (cookie) | 200 | 401 |

**Cookie spec for login:**
```python
response.set_cookie(
    key="session_id", value=session_id,
    httponly=True, samesite="lax", path="/"
)
```

**Cookie deletion for logout:**
```python
response.delete_cookie("session_id")
```

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.auth.router import router
routes = {r.path for r in router.routes}
assert '/auth/register' in routes
assert '/auth/login' in routes
assert '/auth/logout' in routes
print('Auth router routes OK')
"
```

**Acceptance criteria:**
- [ ] All 3 routes defined
- [ ] `/auth/register` returns 201
- [ ] `/auth/login` sets `session_id` HttpOnly cookie
- [ ] `/auth/logout` deletes cookie and destroys Redis session
- [ ] Test command exits 0

---

### ✅ Task 15 — Write Users Domain (`schemas`, `repository`, `service`)

**Files:**
- `services/user-service/app/users/schemas.py`
- `services/user-service/app/users/repository.py`
- `services/user-service/app/users/service.py`

**`users/schemas.py`:** `UserProfile` with `id`, `username`, `email`, `created_at`

**`users/repository.py`:** `get_user_by_id(db, user_id) → User | None`

**`users/service.py`:**
```python
async def get_profile(db, user_id: str) -> User:
    user = await users_repo.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("user")
    return user
```

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.users.schemas import UserProfile
from app.users.repository import get_user_by_id
from app.users.service import get_profile
import inspect
assert inspect.iscoroutinefunction(get_profile)
print('Users domain OK')
"
```

**Acceptance criteria:**
- [ ] All 3 files exist and importable
- [ ] `get_profile` raises `NotFoundError` when user missing
- [ ] Test command exits 0

---

### ✅ Task 16 — Write `app/users/router.py`

**File:** `services/user-service/app/users/router.py`

**Endpoint:**

| Method | Path | Auth | Success |
|---|---|---|---|
| `GET` | `/users/me` | Yes | 200 + `UserProfile` |

**Uses:** `get_current_user` dependency from `app.dependencies`

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.users.router import router
routes = {r.path for r in router.routes}
assert '/users/me' in routes
print('Users router OK')
"
```

**Acceptance criteria:**
- [ ] Route `/users/me` defined
- [ ] Uses `get_current_user` as dependency
- [ ] Returns `SuccessResponse[UserProfile]`
- [ ] Test command exits 0

---

### ✅ Task 17 — Write `app/main.py`

**File:** `services/user-service/app/main.py`

**What:** FastAPI app with lifespan hooks and 3 global exception handlers.

**Lifespan hooks:**
1. `connect_db()` + `connect_redis()` on startup
2. `close_redis()` + `close_db()` on shutdown

**Exception handlers:**
1. `AppException` → structured JSON error (status from exception)
2. `RequestValidationError` → 422 `VALIDATION_ERROR`
3. Generic `Exception` → 500 `INTERNAL_ERROR`

**Include routers:**
```python
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
```

**Test / Verify:**
```bash
cd services/user-service
python -c "
from app.main import app
routes = {r.path for r in app.routes}
assert '/auth/register' in routes
assert '/users/me' in routes
print('main.py OK — all routes mounted')
"
```

**Acceptance criteria:**
- [ ] App starts without import errors
- [ ] Both routers mounted
- [ ] All 3 exception handlers registered
- [ ] Test command exits 0

---

### ✅ Task 18 — Add `user-service` to `docker-compose.yml`

**What:** Add the user-service container entry to `docker-compose.yml`.

**Add:**
```yaml
user-service:
  build: ./services/user-service
  ports:
    - "8001:8001"
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    SESSION_TTL_SECONDS: ${SESSION_TTL_SECONDS}
  volumes:
    - ./services/shared:/app/shared:ro
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

**Test / Verify:**
```bash
docker compose config --quiet   # validate YAML
docker compose build user-service
docker compose up -d user-service
sleep 5
curl -f http://localhost:8001/docs   # FastAPI docs should be reachable
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] `docker compose build user-service` exits 0
- [ ] `GET http://localhost:8001/docs` returns 200
- [ ] Service starts without crash in `docker compose logs user-service`

---

### ✅ Task 19 — Write `tests/conftest.py`

**File:** `services/user-service/tests/conftest.py`

**What:** Pytest fixtures for async test client + in-memory test DB + Redis mock.

**Fixtures to provide:**

| Fixture | Scope | What it does |
|---|---|---|
| `client` | function | `AsyncClient` pointing at test app |
| `db` | function | In-memory SQLite async session (or test PG) |
| `redis_mock` | function | `fakeredis.aioredis` instance |

**Dependencies:**
```
# Add to requirements.txt (test deps)
fakeredis==2.21.3
pytest-asyncio==0.23.5
httpx==0.27.0
```

**Test / Verify:**
```bash
cd services/user-service
pytest tests/conftest.py --collect-only
# should show no errors
```

**Acceptance criteria:**
- [ ] `conftest.py` exists and `pytest --collect-only` does not error
- [ ] `client` fixture returns an `AsyncClient`
- [ ] `redis_mock` fixture returns a fake Redis

---

### ✅ Task 20 — Write `tests/test_auth.py` and Run

**File:** `services/user-service/tests/test_auth.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_register_success` | Valid data | 201, user in response |
| `test_register_duplicate_email` | Same email twice | 409 CONFLICT |
| `test_login_success_sets_cookie` | Valid credentials | 200, `session_id` cookie set |
| `test_login_wrong_password` | Wrong password | 401 UNAUTHORIZED |
| `test_login_unknown_email` | Email not found | 401 UNAUTHORIZED |
| `test_logout_destroys_session` | Valid session → logout | 200, cookie cleared |
| `test_logout_unauthenticated` | No cookie | 401 UNAUTHORIZED |
| `test_session_expiry` | Expired/missing session key in Redis | 401 UNAUTHORIZED |

**Run:**
```bash
cd services/user-service
pytest tests/test_auth.py -v
```

**Acceptance criteria:**
- [ ] All 8 tests pass ✅
- [ ] `pytest tests/test_auth.py -v` exits 0
- [ ] No skipped tests

---

### ✅ Task 21 — Write `tests/test_users.py` and Run

**File:** `services/user-service/tests/test_users.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_get_me_authenticated` | Valid session cookie | 200, user profile in response |
| `test_get_me_no_cookie` | No cookie at all | 401 UNAUTHORIZED |
| `test_get_me_invalid_session` | Cookie with unknown session ID | 401 UNAUTHORIZED |

**Run:**
```bash
cd services/user-service
pytest tests/test_users.py -v
```

**Acceptance criteria:**
- [ ] All 3 tests pass ✅
- [ ] `pytest tests/test_users.py -v` exits 0

---

### ✅ Final: Run Full Test Suite

```bash
cd services/user-service
pytest tests/ -v --tb=short
```

**Acceptance criteria:**
- [ ] All 11 tests pass (8 auth + 3 users)
- [ ] Zero failures, zero errors

---

## Phase Complete Checklist

Before marking Phase 2 as ✅ done in `COPILOT.md`:

- [ ] All 21 tasks above are ✅ done
- [ ] `pytest tests/ -v` — 11 tests passing, 0 failing
- [ ] `GET http://localhost:8001/docs` reachable
- [ ] `POST /auth/register` creates a user
- [ ] `POST /auth/login` sets `session_id` HttpOnly cookie
- [ ] `GET /users/me` returns user profile with valid session
- [ ] `POST /auth/logout` destroys session
- [ ] Alembic migration ran — `users` table exists in PostgreSQL

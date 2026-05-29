# User Service — Complete Technical Reference

## 1. What Is This Service?

The **user-service** is the authentication and identity microservice. It is the **only** service that
knows about passwords and user accounts. Every other service trusts the session cookie that this
service issues — they never receive or store passwords.

**Port:** `8001` (internal Docker network: `user-service:8001`)  
**Database:** PostgreSQL (`userdb`)  
**Cache:** Redis DB 0 (`redis://redis:6379/0`)  
**Framework:** FastAPI + SQLAlchemy (async) + asyncpg

---

## 2. Folder Structure

```
user-service/
├── app/
│   ├── main.py              ← FastAPI app factory, lifespan hooks, global error handlers
│   ├── config.py            ← Pydantic-Settings (reads .env)
│   ├── database.py          ← SQLAlchemy async engine + session factory + get_db()
│   ├── redis_client.py      ← Singleton Redis connection + get_redis()
│   ├── models.py            ← User SQLAlchemy ORM model
│   ├── exceptions.py        ← Service-specific exception classes
│   │
│   ├── auth/                ← Authentication domain (register / login / logout)
│   │   ├── handler/
│   │   │   └── router.py    ← HTTP routes only — calls service, never DB directly
│   │   ├── utils/
│   │   │   ├── service.py   ← Business logic (hash/verify password, create session)
│   │   │   ├── cache.py     ← Redis session helpers (set/get/refresh/delete)
│   │   │   └── schemas.py   ← Pydantic request/response models
│   │   └── dao/
│   │       └── repository.py← SQLAlchemy queries (get_by_email, get_by_username, create_user)
│   │
│   └── users/               ← User profile domain (read own profile)
│       ├── handler/
│       │   └── router.py    ← HTTP routes only
│       ├── utils/
│       │   ├── service.py   ← Business logic (fetch + validate user)
│       │   └── schemas.py   ← Pydantic response models
│       └── dao/
│           └── repository.py← SQLAlchemy queries (get_user_by_id)
│
├── migrations/              ← Alembic database migrations
│   └── versions/
│       └── 0001_create_users_table.py
├── tests/
│   ├── conftest.py          ← pytest fixtures (in-memory SQLite + mock Redis)
│   ├── test_auth.py         ← 7 tests for register/login/logout
│   └── test_users.py        ← 3 tests for /users/me
├── Dockerfile
├── alembic.ini
├── requirements.txt
└── pytest.ini
```

---

## 3. Three-Layer Architecture

This service strictly follows the **handler → utils → dao** pattern:

```
HTTP Request
    │
    ▼
handler/router.py       ← Receives HTTP, validates schema, calls service, returns response
    │                      Never touches DB or Redis directly
    ▼
utils/service.py        ← All business logic lives here
    │                      Calls dao/ for DB and utils/cache.py for Redis
    ├──► utils/cache.py  ← Redis-only helpers (session CRUD)
    └──► dao/repository.py ← DB-only helpers
    │
    ▼
dao/repository.py       ← Raw SQLAlchemy queries only. No logic, just DB I/O.
```

**Rule:** Each layer can only call the layer below it. `handler` never imports `dao` directly.

---

## 4. Configuration (config.py)

Reads from `.env` file via Pydantic Settings:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@postgres:5432/userdb` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://redis:6379/0` | Redis DB 0 (user sessions) |
| `SESSION_TTL` | `86400` | Session lifetime in seconds (24 hours) |
| `DEBUG` | `False` | Enables SQLAlchemy query logging |

---

## 5. Database (database.py)

Uses **SQLAlchemy async** with `asyncpg` driver:

```python
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)
```

`get_db()` is a FastAPI dependency that yields an `AsyncSession` per request and auto-closes it.

---

## 6. Database Schema (models.py + Migration)

### Table: `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Unique user identifier |
| `username` | VARCHAR(50) | UNIQUE, NOT NULL | Display name (3–50 chars) |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Login email |
| `password_hash` | VARCHAR(60) | NOT NULL | bcrypt hash (never plain text) |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Account creation time |
| `updated_at` | TIMESTAMPTZ | DEFAULT now(), ON UPDATE | Last modification time |

**Indexes:** `idx_users_email`, `idx_users_username` (for fast lookup)

### Migration (Alembic)

The migration is in `migrations/versions/0001_create_users_table.py`.
Run automatically in Docker via `CMD`: `alembic upgrade head && uvicorn ...`

---

## 7. Redis Session Design (utils/cache.py)

Sessions are stored in **Redis DB 0** with the following pattern:

| Key | Value | TTL |
|---|---|---|
| `session:{UUID}` | user_id (string UUID) | 86400s (24h) |

**Sliding Window:** Every authenticated request calls `refresh_session()`, which resets the TTL.
This means sessions expire only after 24 hours of **inactivity**, not 24 hours from login.

```
User logs in                → redis.set("session:abc123", user_id, ex=86400)
User makes any request      → redis.expire("session:abc123", 86400)  ← TTL reset
User inactive for 24h       → key auto-expires
User logs out               → redis.delete("session:abc123")
```

---

## 8. API Endpoints

### Health Check

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service health check |

**Response:**
```json
{ "status": "ok", "service": "user-service" }
```

---

### Auth Endpoints (`/auth`)

#### POST `/auth/register`

Registers a new user account.

**Request Body:**
```json
{
  "username": "alice",       // 3–50 characters
  "email": "alice@example.com",
  "password": "mypassword"   // 8–72 characters
}
```

**Success Response — 201 Created:**
```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "alice",
    "email": "alice@example.com",
    "created_at": "2024-01-15T10:30:00.000000"
  }
}
```

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 409 | `CONFLICT` | Email already registered |
| 409 | `CONFLICT` | Username already taken |
| 422 | `VALIDATION_ERROR` | Invalid email format, password too short, etc. |

**Internal Flow:**
```
POST /auth/register
    → auth/handler/router.py → auth_service.register(db, data)
        → repo.get_by_email(db, email)   ← check email uniqueness
        → repo.get_by_username(db, username) ← check username uniqueness
        → bcrypt.hashpw(password, salt)   ← hash password (never stored plain)
        → repo.create_user(db, username, email, hash)
    ← return UserResponse
```

---

#### POST `/auth/login`

Verifies credentials and creates a session.

**Request Body:**
```json
{
  "email": "alice@example.com",
  "password": "mypassword"
}
```

**Success Response — 200 OK:**
```json
{
  "data": { "message": "logged in" }
}
```

**Also sets an HTTP cookie:**
```
Set-Cookie: session_id=<UUID>; HttpOnly; SameSite=Lax; Path=/
```

> **Important:** The cookie is `HttpOnly` (JavaScript cannot read it) and `SameSite=Lax` (CSRF protection). The browser sends it automatically on every subsequent request.

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 401 | `UNAUTHORIZED` | Email not found or wrong password |
| 422 | `VALIDATION_ERROR` | Invalid request format |

**Internal Flow:**
```
POST /auth/login
    → auth/handler/router.py → auth_service.login(db, redis, data)
        → repo.get_by_email(db, email)      ← fetch user
        → bcrypt.checkpw(plain, hashed)     ← verify password
        → cache.set_session(redis, user_id) ← generate UUID session_id, store in Redis
    ← response.set_cookie(session_id=...)
```

---

#### POST `/auth/logout`

Destroys the current session.

**Auth Required:** Yes (must have valid `session_id` cookie)

**Success Response — 200 OK:**
```json
{
  "data": { "message": "logged out" }
}
```

Also clears the `session_id` cookie from the browser.

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 401 | `UNAUTHORIZED` | No cookie or expired session |

**Internal Flow:**
```
POST /auth/logout
    → _require_session() dependency:
        → request.cookies.get("session_id")
        → cache.get_session(redis, session_id) ← verify session exists
        → cache.refresh_session(redis, session_id) ← reset TTL
    → auth_service.logout(redis, session_id)
        → cache.delete_session(redis, session_id) ← destroy session
    ← response.delete_cookie("session_id")
```

---

### User Profile Endpoints (`/users`)

#### GET `/users/me`

Returns the currently logged-in user's profile.

**Auth Required:** Yes (must have valid `session_id` cookie)

**Success Response — 200 OK:**
```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "alice",
    "email": "alice@example.com",
    "created_at": "2024-01-15T10:30:00.000000"
  }
}
```

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 401 | `UNAUTHORIZED` | No session cookie or expired session |
| 404 | `NOT_FOUND` | User ID from session not found in DB (account deleted) |

**Internal Flow:**
```
GET /users/me
    → _get_current_user_id() dependency:
        → read session_id from cookie
        → cache.get_session(redis, session_id) → returns user_id string
        → cache.refresh_session(redis, session_id) ← sliding TTL
    → users_service.get_me(db, user_id)
        → repo.get_user_by_id(db, user_id) ← fetch from PostgreSQL
    ← return UserProfileResponse
```

---

## 9. Error Response Format (Global)

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
| `UNAUTHORIZED` | 401 | No session, expired session, wrong password |
| `CONFLICT` | 409 | Duplicate email or username |
| `NOT_FOUND` | 404 | User not found |
| `VALIDATION_ERROR` | 422 | Invalid request body (Pydantic fails) |

---

## 10. Authentication Dependency Flow

Both routers use a local dependency function `_require_session()` / `_get_current_user_id()` that:
1. Reads `session_id` cookie from the request
2. Looks it up in Redis → gets `user_id`
3. Refreshes the TTL (sliding window)
4. Returns `(session_id, user_id)` tuple

If any step fails, raises `AuthError` → caught by `AppException` handler → 401 response.

---

## 11. Exceptions Hierarchy

```
shared.exceptions.AppException (base)
    ├── AuthError        → 401 UNAUTHORIZED
    ├── NotFoundError    → 404 NOT_FOUND
    └── ConflictError    → 409 CONFLICT

Service-specific (app/exceptions.py):
    EmailConflictError(ConflictError)     → "Email already registered"
    UsernameConflictError(ConflictError)  → "Username already taken"
    UserNotFoundError(NotFoundError)      → "user not found"
    InvalidCredentialsError(AuthError)    → "Invalid email or password"
```

---

## 12. Startup & Shutdown (Lifespan)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()    # ping PostgreSQL to verify connection
    await connect_redis() # create Redis connection pool
    yield
    await close_redis()   # graceful close
    await close_db()      # dispose SQLAlchemy engine
```

The app starts connections once at boot, not per-request.

---

## 13. Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY migrations/ ./migrations/
COPY app/ ./app/
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
```

**Key points:**
- Runs `alembic upgrade head` first on every container start (safe — migration is idempotent)
- Then starts uvicorn on port 8001
- `shared/` module is bind-mounted from host at `/app/shared` (see docker-compose)

---

## 14. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `sqlalchemy[asyncio]` | 2.0.28 | Async ORM |
| `asyncpg` | 0.29.0 | Async PostgreSQL driver |
| `redis[asyncio]` | 5.0.3 | Async Redis client |
| `bcrypt` | 4.1.2 | Password hashing (cost factor built-in) |
| `pydantic[email]` | 2.6.4 | Request/response validation |
| `pydantic-settings` | 2.2.1 | Config from environment |
| `alembic` | 1.13.1 | Database migrations |

---

## 15. Testing

**Test runner:** `pytest` with `pytest-asyncio`

**Test strategy:**
- **Database:** SQLite in-memory (`aiosqlite`) — no PostgreSQL needed for tests
- **Redis:** Python `dict` acting as mock Redis store (not a real Redis instance)
- **FastAPI `dependency_overrides`:** Injects mock DB session and mock Redis

**Test fixtures (conftest.py):**
- `fake_redis_store` — plain Python dict
- `mock_redis` — object with async `get`, `set`, `expire`, `delete` that operate on the dict
- `client` — `httpx.AsyncClient` pointed at the FastAPI app with overridden dependencies

**Test coverage:**

| File | Tests | What Is Tested |
|---|---|---|
| `test_auth.py` | 7 tests | register success, duplicate email 409, duplicate username 409, login success + cookie, wrong password 401, unknown email 401, logout destroys session |
| `test_users.py` | 3 tests | GET /users/me authenticated success, unauthenticated 401, expired session 401 |

**Run tests:**
```bash
cd backend/user-service
python -m pytest tests/ -q
# Expected: 10 passed
```

---

## 16. Data Flow Diagram — Full Register → Login → Authenticated Request

```
CLIENT                  NGINX              USER-SERVICE          POSTGRES    REDIS
  │                       │                    │                    │          │
  │── POST /auth/register ──►                  │                    │          │
  │                       │──► router.py       │                    │          │
  │                       │      └─ service.register()              │          │
  │                       │           ├─ get_by_email() ───────────►│          │
  │                       │           ├─ get_by_username() ─────────►│         │
  │                       │           ├─ bcrypt.hashpw()            │          │
  │                       │           └─ create_user() ────────────►│          │
  │◄── 201 {data: user} ──┤                    │                    │          │
  │                       │                    │                    │          │
  │── POST /auth/login ───►                    │                    │          │
  │                       │──► router.py       │                    │          │
  │                       │      └─ service.login()                 │          │
  │                       │           ├─ get_by_email() ───────────►│          │
  │                       │           ├─ bcrypt.checkpw()           │          │
  │                       │           └─ cache.set_session() ─────────────────►│
  │◄── 200 + Set-Cookie ──┤                    │                    │          │
  │                       │                    │                    │          │
  │── GET /users/me ──────►  (with cookie)     │                    │          │
  │                       │──► _get_current_user_id()               │          │
  │                       │      ├─ cache.get_session() ──────────────────────►│
  │                       │      │           (returns user_id)       │          │
  │                       │      └─ cache.refresh_session() ─────────────────►│
  │                       │         service.get_me()                 │          │
  │                       │           └─ repo.get_user_by_id() ─────►│          │
  │◄── 200 {data: user} ──┤                    │                    │          │
```

---

## 17. Security Notes

1. **Passwords are never stored or transmitted in plaintext.** Only bcrypt hashes are in the DB.
2. **Session IDs are UUID v4** — cryptographically random, unguessable.
3. **`HttpOnly` cookie** — cannot be read by JavaScript, prevents XSS session theft.
4. **`SameSite=Lax`** — prevents CSRF on cross-site requests that change state.
5. **Timing-safe comparison** — `bcrypt.checkpw` is constant-time to prevent timing attacks.
6. **Sliding TTL** — sessions expire after inactivity, not from creation.

# Phase 2 — User Service

## Goal
A standalone FastAPI microservice that handles user registration, login, logout, and profile retrieval. Uses **bcrypt** for password hashing and **Redis** for server-side session storage.

---

## Service Details

| Property | Value |
|---|---|
| Service name | `user-service` |
| Port | `8001` |
| Framework | FastAPI (Python) |
| Database | PostgreSQL (`users` table) |
| Session store | Redis (`session:{sessionId}`) |
| Tests | Yes — auth flows |

---

## Folder Structure

```
services/user-service/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py          ← FastAPI app entry point (lifespan, exception handlers)
│   ├── config.py        ← env-based config (pydantic BaseSettings)
│   ├── database.py      ← PostgreSQL connection (SQLAlchemy async)
│   ├── redis_client.py  ← Redis connection
│   ├── models.py        ← SQLAlchemy ORM models
│   ├── exceptions.py    ← re-exports shared exceptions + any service-specific ones
│   ├── dependencies.py  ← re-exports shared get_db, get_redis, get_current_user
│   ├── auth/
│   │   ├── router.py    ← /auth/* endpoints
│   │   ├── service.py   ← business logic
│   │   ├── repository.py ← DB queries only
│   │   ├── cache.py     ← Redis session operations
│   │   └── schemas.py   ← auth-specific Pydantic schemas
│   └── users/
│       ├── router.py    ← /users/* endpoints
│       ├── service.py
│       ├── repository.py
│       └── schemas.py
└── tests/
    ├── conftest.py
    ├── test_auth.py
    └── test_users.py
```

---

## API Endpoints

### Auth

```
POST /auth/register
  Body: { "username": str, "email": str, "password": str }
  Response 201: { "data": { "id": uuid, "username": str, "email": str }, "message": "success" }
  Error 409: { "error": "CONFLICT", "message": "Email already registered" }

POST /auth/login
  Body: { "email": str, "password": str }
  Response 200: { "data": { "message": "logged in" }, "message": "success" }
  Sets cookie: session_id=<uuid>; HttpOnly; SameSite=Lax
  Error 401: { "error": "UNAUTHORIZED", "message": "Invalid credentials" }

POST /auth/logout
  Requires: session cookie
  Response 200: { "data": { "message": "logged out" }, "message": "success" }
  Destroys Redis session key

GET /users/me
  Requires: session cookie
  Response 200: { "data": { "id": uuid, "username": str, "email": str, "created_at": str }, "message": "success" }
  Error 401: { "error": "UNAUTHORIZED", "message": "Not authenticated" }
```

---

## PostgreSQL Schema

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username     VARCHAR(50)  UNIQUE NOT NULL,
    email        VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(60) NOT NULL,   -- bcrypt hash
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

---

## Session Design (Redis)

```
Key   : session:{sessionId}      (sessionId = random UUID generated on login)
Value : userId (UUID string)
TTL   : 86400 seconds (24 hours, reset on each request)

Cookie sent to browser:
  Name     : session_id
  Value    : <sessionId UUID>
  HttpOnly : true      (not accessible via JS)
  SameSite : Lax
  Path     : /
```

### Session Middleware (shared across all services)

All services that need auth will use a shared `get_current_user` dependency:

```python
# shared/auth_middleware.py
async def get_current_user(
    request: Request,
    redis: Redis = Depends(get_redis)
) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = await redis.get(f"session:{session_id}")
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired")
    await redis.expire(f"session:{session_id}", 86400)  # sliding TTL
    return user_id
```

---

## Password Hashing

```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

## requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
redis[asyncio]==5.0.3
bcrypt==4.1.2
pydantic-settings==2.2.1
alembic==1.13.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
```

---

## Tests

```
tests/test_auth.py
  ✅ test_register_success
  ✅ test_register_duplicate_email_returns_409
  ✅ test_login_success_sets_cookie
  ✅ test_login_wrong_password_returns_401
  ✅ test_logout_destroys_session
  ✅ test_get_me_authenticated
  ✅ test_get_me_unauthenticated_returns_401
  ✅ test_session_expires_returns_401
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| `POST /auth/register` | Sync (awaited) | Must confirm user created before returning |
| `POST /auth/login` | Sync (awaited) | Must verify password + set session before responding |
| `GET /users/me` | Sync (awaited) | Must verify session + fetch user before responding |
| Redis session read | Async (await) | Non-blocking I/O via `redis[asyncio]` |
| PostgreSQL query | Async (await) | Non-blocking I/O via `asyncpg` |

---

## Pydantic Schemas

Key field constraints from LLD §5.3:

```python
# auth/schemas.py
from pydantic import BaseModel, Field, EmailStr

class RegisterRequest(BaseModel):
    username: str   = Field(min_length=3,  max_length=50)
    email:    EmailStr
    password: str   = Field(min_length=8,  max_length=72)

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str   = Field(min_length=8,  max_length=72)

class UserResponse(BaseModel):
    id:         str
    username:   str
    email:      str
    created_at: str
```

---

## Standard Response Format

All endpoints wrap responses in `SuccessResponse` from `shared/schemas.py` (see **shared-patterns.md Section 5**):

```python
# router.py example
from shared.schemas import SuccessResponse

@router.post("/register", status_code=201, response_model=SuccessResponse[UserResponse])
async def register(data: RegisterRequest, ...):
    user = await auth_service.register(data)
    return SuccessResponse(data=UserResponse.model_validate(user))
```

```json
// POST /auth/register → 201
{ "data": { "id": "uuid", "username": "alice", "email": "alice@example.com" }, "message": "success" }

// POST /auth/login → 401
{ "error": "UNAUTHORIZED", "message": "Invalid credentials" }

// POST /auth/register → 409
{ "error": "CONFLICT", "message": "Email already registered" }
```

---

## main.py

Follows the standard template from **shared-patterns.md Section 3** — lifespan hooks connect/disconnect DB and Redis, and global exception handlers convert `AppException` to structured JSON error responses:

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from shared.exceptions import AppException
from app.database import connect_db, close_db
from app.redis_client import connect_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await connect_redis()
    yield
    await close_redis()
    await close_db()

app = FastAPI(lifespan=lifespan)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code,
        content={"error": exc.error, "message": exc.message, "detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422,
        content={"error": "VALIDATION_ERROR", "message": "Invalid input", "detail": exc.errors()})
```

---

## References Shared Patterns

| Pattern | shared-patterns.md |
|---|---|
| Layered architecture (Router → Service → Repository → Cache) | Section 1 |
| Shared `services/shared/` module (`dependencies.py`, `exceptions.py`, `schemas.py`) | Section 2 |
| Standard `main.py` (lifespan, global exception handler) | Section 3 |
| Standard `config.py` template | Section 4 |
| Response envelope (`SuccessResponse`, `ErrorResponse`) | Section 5 |

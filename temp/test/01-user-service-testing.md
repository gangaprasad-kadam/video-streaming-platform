# User Service — Complete API Testing Guide (Postman)

## Overview

This guide walks you through testing every API endpoint of the **user-service**
from scratch using Postman. No coding required — just follow the steps in order.

**Base URL:** `http://localhost:8001`  
**Swagger UI:** `http://localhost:8001/docs` (interactive browser UI)

---

## Step 1: Start the Service

Open your terminal and run:

```bash
cd /path/to/project

# Copy .env file if not done already
cp .env.example .env

# Start PostgreSQL, Redis, and user-service
docker compose up -d postgres redis user-service

# Wait 10 seconds, then verify it's running:
curl http://localhost:8001/health
```

**Expected output:**
```json
{"status": "ok", "service": "user-service"}
```

If you see this, the service is running. If not, check logs:
```bash
docker compose logs user-service
```

---

## Step 2: Postman Setup

1. Open **Postman**
2. Click **New** → **Collection** → Name it `User Service Tests`
3. For each test below, click **New Request** inside this collection

**Tip:** Postman automatically stores and sends cookies for `localhost`. After login, you
don't need to manually add any headers — the `session_id` cookie is sent automatically.

---

## API Test 1: Health Check

### Purpose
Verify the service is running and healthy.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8001/health` |
| Body | None |
| Auth | None |

### Steps in Postman
1. Click **New Request**
2. Set method to `GET`
3. Enter URL: `http://localhost:8001/health`
4. Click **Send**

### Expected Response
**Status: 200 OK**
```json
{
  "status": "ok",
  "service": "user-service"
}
```

---

## API Test 2: Register a New User (Success)

### Purpose
Create a new user account.

### Request
| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/auth/register` |
| Body type | `raw` → `JSON` |
| Auth | None required |

### Steps in Postman
1. New Request → `POST`
2. URL: `http://localhost:8001/auth/register`
3. Click **Body** tab → select **raw** → select **JSON** from dropdown
4. Paste this body:
```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "mypassword123"
}
```
5. Click **Send**

### Expected Response
**Status: 201 Created**
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

**Save the `id` value** — you'll see it later in other responses.

### What Happened Internally?
```
POST /auth/register
  → Checked: is "alice@example.com" already in users table? (No)
  → Checked: is "alice" username taken? (No)
  → bcrypt hashed the password (never stored in plain text)
  → Inserted row into users table
  → Returned the new user data (password NOT included in response)
```

---

## API Test 3: Register — Duplicate Email (Error Case)

### Purpose
Verify that registering with the same email gives a 409 conflict.

### Request
Same as Test 2, but with **the same email**, different username:
```json
{
  "username": "alice_copy",
  "email": "alice@example.com",
  "password": "differentpassword123"
}
```

### Expected Response
**Status: 409 Conflict**
```json
{
  "error": "CONFLICT",
  "message": "Email already registered",
  "detail": null
}
```

---

## API Test 4: Register — Duplicate Username (Error Case)

```json
{
  "username": "alice",
  "email": "different@example.com",
  "password": "mypassword123"
}
```

### Expected Response
**Status: 409 Conflict**
```json
{
  "error": "CONFLICT",
  "message": "Username already taken",
  "detail": null
}
```

---

## API Test 5: Register — Validation Error (Error Case)

Short password (less than 8 characters):
```json
{
  "username": "bob",
  "email": "bob@example.com",
  "password": "short"
}
```

### Expected Response
**Status: 422 Unprocessable Entity**
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid input",
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      ...
    }
  ]
}
```

---

## API Test 6: Login (Success)

### Purpose
Authenticate with email + password. Get a session cookie.

### Request
| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/auth/login` |
| Body | JSON |

### Body
```json
{
  "email": "alice@example.com",
  "password": "mypassword123"
}
```

### Steps in Postman
1. New Request → `POST`
2. URL: `http://localhost:8001/auth/login`
3. Body → raw → JSON → paste body above
4. Click **Send**

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "message": "logged in"
  }
}
```

**After this response, check the Cookies tab in Postman:**
- Click **Cookies** (link below the Send button)
- You'll see a cookie for `localhost`: `session_id = <some-UUID>`

**This cookie is automatically sent on all future requests to localhost.**

### What Happened Internally?
```
POST /auth/login
  → Found user in DB by email
  → bcrypt.checkpw(plain_password, stored_hash) → True ✓
  → Generated new UUID session_id
  → Stored in Redis: "session:{UUID}" = "user_id" with 24h TTL
  → Set cookie: session_id={UUID} in response
```

---

## API Test 7: Login — Wrong Password (Error Case)

```json
{
  "email": "alice@example.com",
  "password": "wrongpassword123"
}
```

### Expected Response
**Status: 401 Unauthorized**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid email or password",
  "detail": null
}
```

**Note:** The error message says "email or password" — deliberately vague to not reveal
whether the email exists in the system (security best practice).

---

## API Test 8: Login — Unknown Email (Error Case)

```json
{
  "email": "nobody@example.com",
  "password": "mypassword123"
}
```

### Expected Response
**Status: 401 Unauthorized**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Invalid email or password",
  "detail": null
}
```

Same error as wrong password — you can't tell if the email exists or not.

---

## API Test 9: Get My Profile (Authenticated)

### Purpose
Fetch the currently logged-in user's profile.

> ⚠️ Make sure you did **Test 6 (Login)** first so the session cookie is active.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8001/users/me` |
| Body | None |
| Auth | Session cookie (auto-sent by Postman) |

### Steps in Postman
1. New Request → `GET`
2. URL: `http://localhost:8001/users/me`
3. **DO NOT add any headers or body** — Postman sends the cookie automatically
4. Click **Send**

### Expected Response
**Status: 200 OK**
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

### What Happened Internally?
```
GET /users/me
  → Read "session_id" cookie from request
  → Looked up Redis key "session:{session_id}" → got user_id
  → Reset TTL on session (sliding window — 24h from now)
  → Fetched user from PostgreSQL by user_id
  → Returned user profile
```

---

## API Test 10: Get My Profile — Unauthenticated (Error Case)

### Purpose
Test what happens without a cookie.

### Steps
1. In Postman, click **Cookies** (link below the Send button)
2. Find the `session_id` cookie for `localhost` → **Delete it**
3. Now send `GET http://localhost:8001/users/me`

### Expected Response
**Status: 401 Unauthorized**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Not authenticated",
  "detail": null
}
```

---

## API Test 11: Logout

### Purpose
Destroy the current session.

> ⚠️ Login again first (Test 6) to get a fresh session cookie.

### Request
| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/auth/logout` |
| Body | None |

### Steps
1. New Request → `POST`
2. URL: `http://localhost:8001/auth/logout`
3. Click **Send** (cookie auto-sent)

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "message": "logged out"
  }
}
```

**After logout:**
- The `session_id` cookie is cleared from browser/Postman
- The session key in Redis is deleted
- Trying `GET /users/me` now returns **401**

### Verify it worked
Try `GET /users/me` → should return 401.

---

## Summary of All Tests

| Test # | Method | URL | Auth | Expected Status |
|---|---|---|---|---|
| 1 | GET | `/health` | None | 200 |
| 2 | POST | `/auth/register` | None | 201 ✅ Success |
| 3 | POST | `/auth/register` | None | 409 ❌ Duplicate email |
| 4 | POST | `/auth/register` | None | 409 ❌ Duplicate username |
| 5 | POST | `/auth/register` | None | 422 ❌ Short password |
| 6 | POST | `/auth/login` | None | 200 ✅ Cookie set |
| 7 | POST | `/auth/login` | None | 401 ❌ Wrong password |
| 8 | POST | `/auth/login` | None | 401 ❌ Unknown email |
| 9 | GET | `/users/me` | Cookie | 200 ✅ Profile returned |
| 10 | GET | `/users/me` | No cookie | 401 ❌ Not authenticated |
| 11 | POST | `/auth/logout` | Cookie | 200 ✅ Session destroyed |

---

## Verify Data in the Database

After running the tests, see what's stored in PostgreSQL:

```bash
# Connect to Postgres
docker compose exec postgres psql -U postgres -d videoplatform

# See registered users
SELECT id, username, email, created_at FROM users;

# See that password is hashed (never plain text)
SELECT password_hash FROM users WHERE email = 'alice@example.com';
-- Returns something like: $2b$12$abc123... (bcrypt hash)

# Exit
\q
```

---

## Verify Sessions in Redis

```bash
# Connect to Redis
docker compose exec redis redis-cli

# See all session keys
KEYS session:*

# Check a specific session value (returns user_id)
GET session:<UUID-from-cookie>

# See TTL remaining (in seconds)
TTL session:<UUID>

# Exit
exit
```

After logout, the key should be gone.
After logging in again, a new key appears.
After any authenticated request, the TTL resets to 86400 (24 hours).

---

## Swagger UI (Alternative to Postman)

Visit `http://localhost:8001/docs` in your browser.

You can test all endpoints interactively. However, the Swagger UI **does not handle cookies well**
(it uses the `Authorize` button for Bearer tokens, not cookies). For cookie-based auth,
**Postman is better**.

# Video Service — Complete API Testing Guide (Postman)

## Overview

This guide tests every endpoint of the **video-service** — upload, fetch, list, update metadata,
check status, and internal status updates (simulating what workers do).

**Base URL:** `http://localhost:8002`  
**Swagger UI:** `http://localhost:8002/docs`

> ⚠️ **Prerequisite:** You must be logged in through user-service first.
> The video-service reads the same session cookie that user-service sets.
> Complete `01-user-service-testing.md` Test 6 (Login) before starting here.

---

## Step 1: Start the Services

```bash
cd /path/to/project

# Start infrastructure + both services
docker compose up -d postgres redis kafka zookeeper user-service video-service

# Wait 15-20 seconds, then verify:
curl http://localhost:8002/health
```

**Expected:** `{"status": "ok", "service": "video-service"}`

---

## Login First (Required)

Before any video endpoint test, log in via user-service:

```
POST http://localhost:8001/auth/login
Body: {"email": "alice@example.com", "password": "mypassword123"}
```

This sets the `session_id` cookie. Postman will send it automatically to `localhost:8002` too.

---

## API Test 1: Health Check

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8002/health` |

**Expected (200):**
```json
{"status": "ok", "service": "video-service"}
```

---

## API Test 2: Upload a Video (Success)

### Purpose
Upload a video file. The service saves it to disk and publishes a Kafka event.

### ⚠️ Important: This uses multipart form data, NOT JSON.

### Steps in Postman
1. New Request → `POST`
2. URL: `http://localhost:8002/videos/upload`
3. Click **Body** tab → select **form-data** (NOT raw JSON!)
4. Add these fields:

| Key | Type | Value |
|---|---|---|
| `title` | Text | `My First Video` |
| `description` | Text | `This is a test video` |
| `file` | File | Select any `.mp4` file from your computer |

> **No .mp4?** Create a fake one: `echo "fake video" > test.mp4` — the service saves
> whatever bytes you send (encoding happens later by encoding-worker).

5. Click **Send** (session cookie auto-sent)

### Expected Response
**Status: 201 Created**
```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "My First Video",
    "description": "This is a test video",
    "status": "uploading",
    "creator_id": "user-uuid-here",
    "file_path": "/media/uploads/video-uuid.mp4",
    "hls_path": null,
    "thumbnail_path": null,
    "duration": null,
    "file_size_bytes": 1234,
    "mime_type": "video/mp4",
    "created_at": "2024-01-15T10:35:00"
  }
}
```

**Save the `id` value** — you need it for subsequent tests. Let's call it `VIDEO_ID`.

### What Happened Internally?
```
POST /videos/upload
  → Verified session cookie → got user_id
  → Saved file to /media/uploads/{placeholder}.mp4
  → Inserted row in videos table (status="uploading")
  → Renamed file to /media/uploads/{real-uuid}.mp4
  → Published "video.uploaded" event to Kafka
  → Returned video data
```

---

## API Test 3: Upload — Without Auth (Error Case)

Open Postman's **Cookies** tab → delete `session_id` → retry the upload.

**Expected (401):**
```json
{
  "error": "UNAUTHORIZED",
  "message": "Not authenticated",
  "detail": null
}
```

> **Restore your session:** Log in again at `POST http://localhost:8001/auth/login`

---

## API Test 4: Get Video by ID

### Purpose
Fetch metadata for a single video. Uses Redis cache.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8002/videos/{VIDEO_ID}` |
| Auth | None required (public endpoint) |

Replace `{VIDEO_ID}` with the actual UUID from Test 2.

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "id": "550e8400-...",
    "title": "My First Video",
    "status": "uploading",
    ...
  }
}
```

**Second request (cache hit):**  
Send the exact same request again. The response is identical but served from Redis (no DB query).
You can't see this difference in Postman, but it's ~10x faster.

---

## API Test 5: Get Video — Not Found (Error Case)

```
GET http://localhost:8002/videos/00000000-0000-0000-0000-000000000000
```

**Expected (404):**
```json
{
  "error": "VIDEO_NOT_FOUND",
  "message": "Video with id '00000000-...' not found",
  "detail": null
}
```

---

## API Test 6: List Videos

### Purpose
Get a paginated list of all videos.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8002/videos` |
| Auth | None |

### Expected Response
**Status: 200 OK**
```json
{
  "data": [
    {
      "id": "550e8400-...",
      "title": "My First Video",
      "status": "uploading",
      ...
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Test Pagination
Upload 2 more videos (repeat Test 2 with different titles), then:

```
GET http://localhost:8002/videos?page=1&limit=2
```

**Expected:** 2 items in `data`, `total: 3`

```
GET http://localhost:8002/videos?page=2&limit=2
```

**Expected:** 1 item in `data`, `total: 3`

### Filter by Creator
```
GET http://localhost:8002/videos?creator_id={your-user-id}
```

---

## API Test 7: Update Video Metadata (PATCH)

### Purpose
Update the title and/or description of your video. Only the creator can do this.

### Request
| Field | Value |
|---|---|
| Method | `PATCH` |
| URL | `http://localhost:8002/videos/{VIDEO_ID}` |
| Body | JSON |
| Auth | Session cookie required |

### Body
```json
{
  "title": "Updated Title",
  "description": "New description for my video"
}
```

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "id": "550e8400-...",
    "title": "Updated Title",
    "description": "New description for my video",
    ...
  }
}
```

### Test Partial Update (only title)
```json
{
  "title": "Only Title Changed"
}
```
Description stays the same.

---

## API Test 8: Update — Not Your Video (Error Case)

### Purpose
Test that another user cannot edit your video.

### Steps
1. Register a second user: `POST /auth/register` with different email/username
2. Login as second user: `POST /auth/login` (this changes your session cookie)
3. Try to PATCH the video you uploaded as alice:
```
PATCH http://localhost:8002/videos/{VIDEO_ID}
Body: {"title": "Hijacked!"}
```

**Expected (403):**
```json
{
  "error": "FORBIDDEN",
  "message": "Access denied",
  "detail": null
}
```

4. Login as alice again to restore session.

---

## API Test 9: Get Video Status

### Purpose
Lightweight status check — returns only ID + current status.

### Request
```
GET http://localhost:8002/videos/{VIDEO_ID}/status
```

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "id": "550e8400-...",
    "status": "uploading"
  }
}
```

No Redis cache — always fresh from DB.

---

## API Test 10: Internal Status Update — Simulate Worker

### Purpose
Simulate what the encoding-worker does — advance video through its lifecycle.

> This is an **internal endpoint** not exposed via nginx. Workers call it directly.
> You can call it directly in Postman for testing.

### Step A: Set to "processing"

```
Method: PATCH
URL:    http://localhost:8002/internal/videos/{VIDEO_ID}/status
Body (JSON):
{
  "status": "processing"
}
```

**Expected (200):**
```json
{
  "data": {
    "id": "...",
    "status": "processing",
    "hls_path": null,
    ...
  }
}
```

Verify: `GET /videos/{VIDEO_ID}/status` → `"status": "processing"`

### Step B: Set to "ready" (with HLS path + duration)

```
Method: PATCH
URL:    http://localhost:8002/internal/videos/{VIDEO_ID}/status
Body:
{
  "status": "ready",
  "hls_path": "/media/hls/test-uuid/index.m3u8",
  "duration": 125.5
}
```

**Expected (200):**
```json
{
  "data": {
    "status": "ready",
    "hls_path": "/media/hls/test-uuid/index.m3u8",
    "duration": 125.5,
    ...
  }
}
```

### Step C: Simulate thumbnail-worker (terminal state update)

Video is now "ready". Try adding `thumbnail_path`:

```
Method: PATCH
URL:    http://localhost:8002/internal/videos/{VIDEO_ID}/status
Body:
{
  "status": "processing",
  "thumbnail_path": "/media/thumbnails/test-uuid.jpg"
}
```

**Expected (200) — Key behavior:**
```json
{
  "data": {
    "status": "ready",               ← Status NOT changed (terminal state)
    "thumbnail_path": "/media/thumbnails/test-uuid.jpg",  ← This IS updated
    "hls_path": "/media/hls/test-uuid/index.m3u8",
    "duration": 125.5
  }
}
```

This is the terminal-state fix — status stays "ready" but `thumbnail_path` gets updated.

### Step D: Try "failed" on "ready" (idempotency test)

```
Body: {"status": "failed"}
```

**Expected (200):**
```json
{
  "data": {
    "status": "ready",   ← Still "ready" — terminal state can't go to "failed"
    ...
  }
}
```

---

## Full Test Sequence (Order Matters)

Run these in order to see the complete video lifecycle:

| # | Method | URL | Body | Expected Status |
|---|---|---|---|---|
| 1 | GET | `/health` | — | 200 |
| 2 | POST | `/videos/upload` | multipart form | 201 ✅ status=uploading |
| 3 | POST | `/videos/upload` | no cookie | 401 ❌ |
| 4 | GET | `/videos/{id}` | — | 200 ✅ from DB |
| 5 | GET | `/videos/{id}` | — | 200 ✅ from Redis cache |
| 6 | GET | `/videos/00000000-...` | — | 404 ❌ |
| 7 | GET | `/videos` | — | 200 ✅ list |
| 8 | GET | `/videos?page=1&limit=1` | — | 200 ✅ paginated |
| 9 | PATCH | `/videos/{id}` | update title | 200 ✅ |
| 10 | PATCH | `/videos/{id}` | different user | 403 ❌ |
| 11 | GET | `/videos/{id}/status` | — | 200 ✅ |
| 12 | PATCH | `/internal/videos/{id}/status` | processing | 200 ✅ |
| 13 | PATCH | `/internal/videos/{id}/status` | ready + hls | 200 ✅ |
| 14 | PATCH | `/internal/videos/{id}/status` | thumbnail (terminal) | 200 ✅ status unchanged |
| 15 | PATCH | `/internal/videos/{id}/status` | failed (terminal) | 200 ✅ status unchanged |

---

## Verify in Database

```bash
docker compose exec postgres psql -U postgres -d videoplatform

-- See all videos
SELECT id, title, status, hls_path, thumbnail_path, duration FROM videos;

-- Check your specific video
SELECT * FROM videos WHERE title = 'My First Video';

\q
```

---

## Verify Redis Cache

```bash
docker compose exec redis redis-cli

# See cached video keys (DB 1)
SELECT 1
KEYS video:*

# Check the cached value (JSON)
GET video:{video-uuid}

# After PATCH, the cache is invalidated — key should be gone
# Then GET /videos/{id} again to repopulate cache

exit
```

---

## Verify Kafka Events

```bash
# See messages published to video.uploaded topic
docker compose exec kafka kafka-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic video.uploaded \
  --from-beginning \
  --max-messages 5
```

You'll see JSON messages like:
```json
{
  "videoId": "550e8400-...",
  "creatorId": "user-uuid",
  "filePath": "/media/uploads/video-uuid.mp4",
  "mimeType": "video/mp4",
  "title": "My First Video",
  "uploadedAt": "2024-01-15T10:35:00"
}
```

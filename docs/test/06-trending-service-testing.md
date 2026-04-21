# Trending Service — Complete API Testing Guide (Postman)

## Overview

The **trending-service** combines two things:
1. A **Kafka consumer** that listens for viewer interaction events and updates Redis sorted set scores.
2. Two **HTTP endpoints** to read trending leaderboard and personalised recommendations.

**Base URL:** `http://localhost:8005`  
**Swagger UI:** `http://localhost:8005/docs`

> ⚠️ **No auth required** for trending and recommendation endpoints — they are public read APIs.

---

## Step 1: Start the Services

```bash
cd /path/to/project

docker compose up -d postgres redis kafka zookeeper trending-service

# Wait 15 seconds, then verify:
curl http://localhost:8005/health
```

**Expected:**
```json
{"status": "ok", "service": "trending-service"}
```

Check logs to confirm Kafka consumer connected:
```bash
docker compose logs trending-service
```

Expected log lines:
```
INFO  Trending consumer started — listening on 'viewer-interaction-events'
INFO  Score decay loop started (interval=3600s, factor=0.90)
```

---

## Step 2: Seed Trending Scores (Simulate Viewer Interactions)

The trending service reads scores from a **Redis sorted set** (`trending:scores` in Redis DB 4).
Normally the Kafka consumer fills this, but for testing we seed it directly.

### Approach A — Seed Redis Manually (Fastest)

```bash
docker compose exec redis redis-cli

SELECT 4

# Add 3 videos with different scores
ZADD trending:scores 150.5 "YOUR_REAL_VIDEO_ID"
ZADD trending:scores 87.0  "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ZADD trending:scores 42.3  "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

# Verify they were added
ZREVRANGE trending:scores 0 -1 WITHSCORES

exit
```

> **Tip:** Use your real video ID (from Phase 3 upload test) for the first entry so you can
> see full metadata in the response.

### Approach B — Publish a Kafka Event (Tests the full pipeline)

```bash
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic viewer-interaction-events
```

Type this JSON (one line), press Enter, then Ctrl+C:
```json
{"userId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "videoId": "YOUR_REAL_VIDEO_ID", "action": "PLAY", "videoTs": 0.0, "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc", "sessionId": "sess-001", "timestamp": "2024-01-15T10:00:00"}
```

Watch the trending-service logs — you should see:
```
DEBUG [ffffffff-...] Processed PLAY event for video YOUR_REAL_VIDEO_ID
```

Check Redis DB 4 was updated:
```bash
docker compose exec redis redis-cli
SELECT 4
ZSCORE trending:scores "YOUR_REAL_VIDEO_ID"
# Expected: "1" (PLAY action = +1 score)
exit
```

---

## Score Weights Reference

| Action | Score Delta | When it fires |
|---|---|---|
| `PLAY` | +1.0 | User presses play |
| `WATCH_COMPLETE` | +10.0 | User watches to the end |
| `REWIND` | +3.0 | User rewatches a segment |
| `SEEK` | +1.0 | User seeks to a timestamp |
| `PAUSE` | +0.5 | User pauses |
| `SKIP` | -0.5 | User skips forward |

---

## API Test 1: Health Check

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8005/health` |
| Body | None |
| Auth | None |

**Expected (200):**
```json
{"status": "ok", "service": "trending-service"}
```

---

## API Test 2: Get Trending — Empty List

Before seeding any data:

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8005/trending` |

**Expected (200):**
```json
{
  "data": {
    "videos": [],
    "total": 0
  }
}
```

---

## API Test 3: Get Trending — With Results

After seeding Redis scores (Step 2 above), the trending endpoint returns ranked videos.
Only `status = ready` videos are included — ghost entries in Redis (deleted videos) are silently skipped.

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8005/trending` |

**Expected (200):**
```json
{
  "data": {
    "videos": [
      {
        "video_id": "YOUR_REAL_VIDEO_ID",
        "title": "My Uploaded Video",
        "creator_id": "cccccccc-...",
        "thumbnail_path": "/media/thumbnails/...",
        "duration": 45.2,
        "score": 150.5,
        "rank": 1
      }
    ],
    "total": 1
  }
}
```

> The other two seeded IDs (`aaaa...`, `bbbb...`) won't appear because they don't exist in the
> PostgreSQL `videos` table. Only your real uploaded video (which is `ready`) shows up.

---

## API Test 4: Get Trending with Custom Limit

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8005/trending?limit=5` |

**Expected (200):** Same structure, but capped at 5 results max.

**Validation bounds:**
- `limit=0` → **422 Validation Error** (minimum is 1)
- `limit=101` → **422 Validation Error** (maximum is 100)

```
GET http://localhost:8005/trending?limit=0
```
Expected: **422** — `{"error": "VALIDATION_ERROR", ...}`

---

## API Test 5: Recommendations — No Watch History

Call recommendations for a user with no watch history.

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8005/trending/recommendations/ffffffff-ffff-ffff-ffff-ffffffffffff` |

**Expected (200):**
```json
{
  "data": {
    "user_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "videos": [
      {
        "video_id": "YOUR_REAL_VIDEO_ID",
        "title": "My Uploaded Video",
        "reason": "trending"
      }
    ],
    "total": 1
  }
}
```

Since the user has no history, the 40% creator-based slice is empty. Only the trending slice fills the response.

---

## API Test 6: Recommendations — With Watch History (Kafka PLAY event)

Publish a **PLAY event** via Kafka to seed the watch history:

```bash
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic viewer-interaction-events
```

```json
{"userId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "videoId": "YOUR_REAL_VIDEO_ID", "action": "PLAY", "videoTs": 0.0, "creatorId": "YOUR_CREATOR_ID", "sessionId": "sess-001", "timestamp": "2024-01-15T10:00:00"}
```

Wait 2-3 seconds for the consumer to process it.

Now call recommendations again:
```
GET http://localhost:8005/trending/recommendations/ffffffff-ffff-ffff-ffff-ffffffffffff
```

**Expected change:** The video you just "played" no longer appears in the trending slice (it's now in watch history → filtered out). The creator-based slot may show other videos by that creator (if any exist in `status=ready`).

### Verify watch_history was inserted:
```bash
docker compose exec postgres psql -U postgres -d videoplatform

SELECT user_id, video_id, creator_id, watched_at
FROM watch_history
WHERE user_id = 'ffffffff-ffff-ffff-ffff-ffffffffffff';

\q
```

---

## API Test 7: Score Decay Verification

The decay loop runs every **hour** in production. To test it manually, seed a score and then
call the Redis pipeline directly:

```bash
docker compose exec redis redis-cli

SELECT 4

# Check current score
ZSCORE trending:scores "YOUR_REAL_VIDEO_ID"
# e.g. returns "150.5"

# Simulate one decay cycle manually (multiply by 0.9):
# 150.5 * 0.9 = 135.45
ZADD trending:scores 135.45 "YOUR_REAL_VIDEO_ID"

ZSCORE trending:scores "YOUR_REAL_VIDEO_ID"
# Now returns "135.45"

exit
```

After enough decay cycles (days), scores drop below 0.01 and are auto-removed from the set.

---

## Test Summary

| # | Method | URL | Expected |
|---|---|---|---|
| 1 | GET | `/health` | 200 ok |
| 2 | GET | `/trending` (empty) | 200 empty list |
| 3 | GET | `/trending` (seeded) | 200 ranked videos |
| 4 | GET | `/trending?limit=5` | 200 capped at 5 |
| 5 | GET | `/trending?limit=0` | 422 Validation Error |
| 6 | GET | `/trending/recommendations/{userId}` (no history) | 200 trending-only |
| 7 | GET | `/trending/recommendations/{userId}` (after PLAY) | 200 hybrid |
| 8 | DB check | `SELECT * FROM watch_history` | Row inserted on PLAY |

---

## Understanding the Response

### Trending endpoint
```json
{
  "data": {
    "videos": [
      {
        "video_id": "...",      ← UUID
        "title": "...",         ← from videos table
        "creator_id": "...",    ← from videos table
        "thumbnail_path": "...", ← from videos table (null if not encoded yet)
        "duration": 45.2,       ← from videos table (null if not encoded yet)
        "score": 150.5,         ← from Redis sorted set
        "rank": 1               ← 1-based ranking (1 = most popular)
      }
    ],
    "total": 1
  }
}
```

### Recommendations endpoint
```json
{
  "data": {
    "user_id": "...",
    "videos": [
      {
        "video_id": "...",
        "title": "...",
        "creator_id": "...",
        "thumbnail_path": "...",
        "duration": 45.2,
        "reason": "trending"   ← "trending" or "creator"
      }
    ],
    "total": 2
  }
}
```

The `reason` field tells you **why** a video was recommended:
- `"trending"` → in the top 60% slice from the global leaderboard
- `"creator"` → from a creator the user has previously watched (40% slice)

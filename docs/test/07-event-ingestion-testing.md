# Event Ingestion Service — Complete API Testing Guide (Postman)

## Overview

The **event-ingestion** service is the single write gateway for all viewer interaction events.
It accepts one HTTP endpoint, applies rate limiting, and publishes to Kafka.

**Base URL:** `http://localhost:8006`  
**Swagger UI:** `http://localhost:8006/docs`

> ⚠️ **No auth cookie required** — events are identified by `userId` in the request body.
> Rate limiting is applied per `userId` (60 events per minute).

---

## Step 1: Start the Services

```bash
cd /path/to/project

docker compose up -d redis kafka zookeeper event-ingestion

# Wait 10 seconds, then verify:
curl http://localhost:8006/health
```

**Expected:**
```json
{"status": "ok", "service": "event-ingestion"}
```

Check logs to confirm Kafka producer connected:
```bash
docker compose logs event-ingestion
```

Expected log lines:
```
INFO     Started server process
INFO     Application startup complete.
```

---

## Step 2: Postman Setup

1. Open **Postman**
2. Click **New** → **Collection** → Name it `Event Ingestion Tests`
3. For each test below, click **New Request** inside this collection

**Tip:** All requests use `Content-Type: application/json`. Postman sets this automatically
when you select **Body → raw → JSON**.

---

## API Test 1: Health Check

### Purpose
Verify the service is running and the Kafka producer is connected.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8006/health` |
| Body | None |
| Auth | None |

### Steps in Postman
1. New Request → `GET`
2. URL: `http://localhost:8006/health`
3. Click **Send**

### Expected Response
**Status: 200 OK**
```json
{
  "status": "ok",
  "service": "event-ingestion"
}
```

---

## API Test 2: Ingest a PLAY Event (Success)

### Purpose
Submit a viewer interaction event. Service returns 202 and publishes to Kafka.

### Request
| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8006/events/interaction` |
| Body type | `raw` → `JSON` |
| Auth | None |

### Steps in Postman
1. New Request → `POST`
2. URL: `http://localhost:8006/events/interaction`
3. Click **Body** tab → select **raw** → select **JSON**
4. Paste this body:
```json
{
  "userId":    "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "videoId":   "YOUR_REAL_VIDEO_ID",
  "action":    "PLAY",
  "videoTs":   0.0,
  "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "sessionId": "sess-001"
}
```
5. Click **Send**

> **Replace `YOUR_REAL_VIDEO_ID`** with an actual video UUID from your upload tests (Phase 3).
> This lets you verify downstream consumers (trending-service, heatmap-aggregator) processed it.

### Expected Response
**Status: 202 Accepted**
```json
{
  "accepted": true,
  "action": "PLAY",
  "videoId": "YOUR_REAL_VIDEO_ID"
}
```

### What Happened Internally?
```
POST /events/interaction
  → Redis: INCR ratelimit:events:ffffffff-... → returns 1 (first event this minute)
  → Redis: EXPIRE ratelimit:events:ffffffff-... 60
  → Kafka: send_and_wait("viewer-interaction-events", payload, key=videoId)
  → 202 response returned immediately
```

### Verify Kafka Received It
```bash
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic viewer-interaction-events \
  --from-beginning \
  --max-messages 1
```

You should see the JSON payload you just sent.

---

## API Test 3: Ingest a WATCH_COMPLETE Event

### Purpose
Test a different action type — highest-weight event.

### Body
```json
{
  "userId":    "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "videoId":   "YOUR_REAL_VIDEO_ID",
  "action":    "WATCH_COMPLETE",
  "videoTs":   120.5,
  "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "sessionId": "sess-001"
}
```

### Expected Response
**Status: 202 Accepted**
```json
{
  "accepted": true,
  "action": "WATCH_COMPLETE",
  "videoId": "YOUR_REAL_VIDEO_ID"
}
```

---

## API Test 4: Ingest a REWIND Event (at specific timestamp)

### Purpose
Test timestamp-aware event — this is what feeds the heatmap at a specific bucket.

### Body
```json
{
  "userId":    "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "videoId":   "YOUR_REAL_VIDEO_ID",
  "action":    "REWIND",
  "videoTs":   142.5,
  "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "sessionId": "sess-001"
}
```

### Expected Response
**Status: 202 Accepted**

After this, check the heatmap-aggregator logs:
```bash
docker compose logs heatmap-aggregator
```

Expected log:
```
INFO  Recorded REWIND (w=3) for video=YOUR_REAL_VIDEO_ID bucket=140s
```

The `videoTs: 142.5` was mapped to bucket 140 (seconds 140–145).

---

## API Test 5: Ingest a SKIP Event (Negative Score)

### Purpose
Test negative-weight event — SKIP reduces the heatmap score for that segment.

### Body
```json
{
  "userId":    "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "videoId":   "YOUR_REAL_VIDEO_ID",
  "action":    "SKIP",
  "videoTs":   30.0,
  "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "sessionId": "sess-001"
}
```

### Expected Response
**Status: 202 Accepted**

Check heatmap-aggregator logs — you should see bucket 30 decremented by 1.

---

## API Test 6: Invalid Action Type (Validation Error)

### Purpose
Verify Pydantic rejects unknown action strings.

### Body
```json
{
  "userId":  "user-1",
  "videoId": "video-1",
  "action":  "INVALID_ACTION"
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
      "type": "literal_error",
      "loc": ["body", "action"],
      "msg": "Input should be 'PLAY', 'WATCH_COMPLETE', 'REWIND', 'SEEK', 'PAUSE' or 'SKIP'",
      "input": "INVALID_ACTION"
    }
  ]
}
```

**Valid actions:** `PLAY`, `WATCH_COMPLETE`, `REWIND`, `SEEK`, `PAUSE`, `SKIP`

---

## API Test 7: Missing Required Fields (Validation Error)

### Purpose
Verify required fields are enforced.

### Body (missing `action`)
```json
{
  "userId":  "user-1",
  "videoId": "video-1"
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
      "type": "missing",
      "loc": ["body", "action"],
      "msg": "Field required"
    }
  ]
}
```

---

## API Test 8: Rate Limit — Simulate Exceeding 60 Events/Minute

### Purpose
Verify that a user is blocked after 60 events in the same 60-second window.

### How to Simulate
The easiest way is to check what the Redis counter looks like and manually set it:

```bash
docker compose exec redis redis-cli

SELECT 5    # event-ingestion uses DB 5

# Check current count for our test user
GET "ratelimit:events:ffffffff-ffff-ffff-ffff-ffffffffffff"
# Returns "5" (from tests 2–5 above, plus any others)

# Manually set it to 60 (the limit)
SET "ratelimit:events:ffffffff-ffff-ffff-ffff-ffffffffffff" 60 EX 60

exit
```

Now send one more event (any valid body with the same `userId`):

```json
{
  "userId":  "ffffffff-ffff-ffff-ffff-ffffffffffff",
  "videoId": "video-1",
  "action":  "PLAY"
}
```

### Expected Response
**Status: 429 Too Many Requests**
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many events from user ffffffff-ffff-ffff-ffff-ffffffffffff. Limit: 60 per minute.",
  "detail": null
}
```

**After 60 seconds**, the Redis key expires and the counter resets. The next request will be accepted.

---

## API Test 9: Rate Limit — Different User is Not Blocked

### Purpose
Verify rate limiting is per-user, not global.

### Body (different `userId`)
```json
{
  "userId":    "11111111-1111-1111-1111-111111111111",
  "videoId":   "YOUR_REAL_VIDEO_ID",
  "action":    "PLAY",
  "videoTs":   0.0
}
```

### Expected Response
**Status: 202 Accepted** (not blocked, different user has a fresh counter)

---

## API Test 10: Optional Fields Use Defaults

### Purpose
Confirm `videoTs`, `creatorId`, `sessionId`, and `timestamp` are all optional.

### Body (minimal — only required fields)
```json
{
  "userId":  "user-minimal",
  "videoId": "video-minimal",
  "action":  "PAUSE"
}
```

### Expected Response
**Status: 202 Accepted**
```json
{
  "accepted": true,
  "action": "PAUSE",
  "videoId": "video-minimal"
}
```

The event is published to Kafka with `videoTs: 0.0`, `creatorId: ""`, `sessionId: ""`,
and `timestamp` auto-set to the current UTC time.

---

## Verify Rate Limit in Redis

```bash
docker compose exec redis redis-cli

SELECT 5   # event-ingestion uses Redis DB 5

# See all rate limit keys
KEYS ratelimit:events:*

# Check count for a specific user
GET "ratelimit:events:ffffffff-ffff-ffff-ffff-ffffffffffff"

# See TTL remaining (resets to 60 on first event, auto-expires)
TTL "ratelimit:events:ffffffff-ffff-ffff-ffff-ffffffffffff"

exit
```

Expected:
- Key exists while user is within the window
- After 60 seconds of no requests, key is gone
- Each new request within the window increments the count

---

## Verify Events Reached Downstream Services

After sending events, verify the full pipeline:

### Check trending-service received and scored it
```bash
docker compose exec redis redis-cli

SELECT 4   # trending-service uses Redis DB 4

ZSCORE trending:scores "YOUR_REAL_VIDEO_ID"
# Should return a score like "1" for PLAY events, "3" for REWIND, etc.

ZREVRANGE trending:scores 0 -1 WITHSCORES
# Shows all videos and their trending scores

exit
```

### Check heatmap-aggregator stored bucket data
```bash
docker compose exec redis redis-cli

SELECT 6   # heatmap-aggregator uses Redis DB 6

# List all heatmap keys for a video
KEYS "heatmap:YOUR_REAL_VIDEO_ID:*"

# Get score for a specific bucket (e.g. bucket 140 after REWIND at videoTs=142.5)
GET "heatmap:YOUR_REAL_VIDEO_ID:total:140"
GET "heatmap:YOUR_REAL_VIDEO_ID:live:140"

# Check TTL on live key (should be ~300 seconds)
TTL "heatmap:YOUR_REAL_VIDEO_ID:live:140"

exit
```

---

## Test Summary

| # | Method | URL | Body | Expected Status |
|---|---|---|---|---|
| 1 | GET | `/health` | None | 200 |
| 2 | POST | `/events/interaction` | PLAY event | 202 ✅ Accepted |
| 3 | POST | `/events/interaction` | WATCH_COMPLETE event | 202 ✅ Accepted |
| 4 | POST | `/events/interaction` | REWIND at 142.5s | 202 ✅ → heatmap bucket=140 |
| 5 | POST | `/events/interaction` | SKIP at 30s | 202 ✅ → negative bucket score |
| 6 | POST | `/events/interaction` | Invalid action | 422 ❌ Validation error |
| 7 | POST | `/events/interaction` | Missing action field | 422 ❌ Field required |
| 8 | POST | `/events/interaction` | After counter=60 | 429 ❌ Rate limited |
| 9 | POST | `/events/interaction` | Different userId | 202 ✅ Not blocked |
| 10 | POST | `/events/interaction` | Minimal body (no optional fields) | 202 ✅ Defaults applied |

---

## Action Reference

| Action | Trending Score Delta | Heatmap Weight | Meaning |
|---|---|---|---|
| `PLAY` | +1.0 | +1 | User pressed play |
| `WATCH_COMPLETE` | +10.0 | +2 | User watched to the end |
| `REWIND` | +3.0 | +3 | User re-watched this segment |
| `SEEK` | +1.0 | +2 | User navigated to this point |
| `PAUSE` | +0.5 | +1 | User paused |
| `SKIP` | -0.5 | -1 | User skipped forward |

> **Note:** Trending score deltas (trending-service) and heatmap weights (heatmap-aggregator)
> use different scales — the same event has different numerical impact in each service.

---

## Swagger UI (Alternative to Postman)

Visit `http://localhost:8006/docs` in your browser.

You can test all endpoints interactively without Postman. Unlike the auth endpoints,
this service has no cookies — everything is in the JSON body, so Swagger works perfectly here.

# Streaming Service — Complete API Testing Guide (Postman)

## Overview

The **streaming-service** serves HLS video content. To test it properly, you first need
a video in "ready" status with a real HLS manifest file on disk. This guide shows both
how to manually simulate the data AND how to test with real encoding.

**Base URL:** `http://localhost:8003`

---

## Step 1: Start the Services

```bash
docker compose up -d postgres redis streaming-service

# Verify:
curl http://localhost:8003/health
```

---

## Setup: Create Test HLS Files

The streaming-service reads real files from `/media/hls/`. You need to either:
- **Option A:** Run the full encoding pipeline (real ffmpeg encoding)
- **Option B:** Manually create fake HLS files for testing

### Option B — Create Fake HLS Files (Fastest for Testing)

```bash
# Get a shell inside the streaming-service container
docker compose exec streaming-service sh

# Create the HLS directory structure
mkdir -p /media/hls/test-video-uuid

# Create a minimal valid m3u8 manifest
cat > /media/hls/test-video-uuid/index.m3u8 << 'EOF'
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:6.000000,
index000.ts
#EXTINF:5.000000,
index001.ts
#EXT-X-ENDLIST
EOF

# Create fake segment files (just some bytes)
echo "fake segment 0 data" > /media/hls/test-video-uuid/index000.ts
echo "fake segment 1 data" > /media/hls/test-video-uuid/index001.ts

exit
```

### Then: Insert a "ready" Video Record in the DB

```bash
docker compose exec postgres psql -U postgres -d videoplatform

INSERT INTO videos (
  id, title, creator_id, file_path, hls_path, status
) VALUES (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'Test Streaming Video',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  '/media/uploads/test.mp4',
  '/media/hls/test-video-uuid/index.m3u8',
  'ready'
);

\q
```

**Your test VIDEO_ID = `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`**

---

## API Test 1: Health Check

```
GET http://localhost:8003/health
```

**Expected (200):** `{"status": "ok", "service": "streaming-service"}`

---

## API Test 2: Get HLS Manifest

### Purpose
Fetch the `.m3u8` playlist file for a ready video.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8003/stream/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/index.m3u8` |
| Auth | None |

### Expected Response
**Status: 200 OK**  
**Content-Type: `application/vnd.apple.mpegurl`**

```
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:6.000000,
index000.ts
#EXTINF:5.000000,
index001.ts
#EXT-X-ENDLIST
```

Notice: Returns **plain text**, not JSON! This is what video players (hls.js) read.

### Second Request (Cache Hit)
Send the same request again → same response from **Redis** (no DB or disk I/O).

**Check Redis:**
```bash
docker compose exec redis redis-cli
SELECT 2
KEYS stream:manifest:*
GET "stream:manifest:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
exit
```

---

## API Test 3: Manifest — Video Not Ready (Error Case)

Insert a processing video:
```bash
docker compose exec postgres psql -U postgres -d videoplatform

INSERT INTO videos (id, title, creator_id, file_path, status)
VALUES (
  'cccccccc-cccc-cccc-cccc-cccccccccccc',
  'Processing Video',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  '/media/uploads/test2.mp4',
  'processing'
);

\q
```

Now request its manifest:
```
GET http://localhost:8003/stream/cccccccc-cccc-cccc-cccc-cccccccccccc/index.m3u8
```

**Expected (425 Too Early):**
```json
{
  "error": "VIDEO_NOT_READY",
  "message": "Video 'cccccccc-...' is not ready for streaming yet",
  "detail": null
}
```

HTTP 425 = "Too Early" — video exists but isn't ready yet.

---

## API Test 4: Manifest — Unknown Video

```
GET http://localhost:8003/stream/00000000-0000-0000-0000-000000000000/index.m3u8
```

**Expected (404 or 425):** Video not found in DB → not ready → same 425 response.

---

## API Test 5: Get HLS Segment

### Purpose
Fetch an individual video segment file.

### Request
```
GET http://localhost:8003/stream/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/index000.ts
```

### Expected Response
**Status: 200 OK**  
**Content-Type: `video/MP2T`**  
**Body:** Binary data (the `.ts` file content)

In Postman, you'll see `[Binary data]` in the response body.
Click **Save Response** → **Save to a file** if you want to inspect it.

### HTTP Range Request Test

Real video players use Range requests for seeking. Test it in Postman:

1. Under **Headers** tab, add:
   - Key: `Range`
   - Value: `bytes=0-9`
2. Send the request

**Expected (206 Partial Content):**
```
Status: 206 Partial Content
Content-Range: bytes 0-9/20
Content-Length: 10
Body: [first 10 bytes of file]
```

---

## API Test 6: Segment — Missing File

```
GET http://localhost:8003/stream/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/index999.ts
```

**Expected (404):**
```json
{
  "error": "NOT_FOUND",
  "message": "Stream file not found: /media/hls/test-video-uuid/index999.ts",
  "detail": null
}
```

---

## API Test 7: Invalidate Cache

### Purpose
Clear the cached manifest for a video (useful after re-encoding).

### Verify cache exists first:
```bash
docker compose exec redis redis-cli
SELECT 2
GET "stream:manifest:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
exit
```

### Request
| Field | Value |
|---|---|
| Method | `DELETE` |
| URL | `http://localhost:8003/stream/internal/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/cache` |

### Expected (200):**
```json
{
  "message": "Cache invalidated for video aaaaaaaa-..."
}
```

### Verify cache is gone:
```bash
docker compose exec redis redis-cli
SELECT 2
GET "stream:manifest:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
# Returns (nil)
exit
```

Next request to `GET /stream/{id}/index.m3u8` will repopulate the cache.

---

## Test Summary

| # | Method | URL | Expected |
|---|---|---|---|
| 1 | GET | `/health` | 200 |
| 2 | GET | `/stream/{id}/index.m3u8` (ready) | 200 Plain text manifest |
| 3 | GET | `/stream/{id}/index.m3u8` (again) | 200 From Redis cache |
| 4 | GET | `/stream/{id}/index.m3u8` (processing) | 425 Too Early |
| 5 | GET | `/stream/{id}/index.m3u8` (unknown) | 425 |
| 6 | GET | `/stream/{id}/index000.ts` | 200 Binary TS data |
| 7 | GET | `/stream/{id}/index000.ts` (Range: bytes=0-9) | 206 Partial |
| 8 | GET | `/stream/{id}/index999.ts` (missing) | 404 |
| 9 | DELETE | `/stream/internal/{id}/cache` | 200 Cache cleared |

---

## Test with a Real Video Player

If you used real HLS files (from Option A — actual encoding), test with hls.js demo:

1. Go to https://hlsjs.video-dev.com/demo/
2. Set stream URL to: `http://localhost:8003/stream/{VIDEO_ID}/index.m3u8`
3. Click **Load**
4. Video should play!

Or use `ffplay`:
```bash
ffplay http://localhost:8003/stream/{VIDEO_ID}/index.m3u8
```

"""
Tests for video-service endpoints.
"""
import io
import pytest

AUTH_COOKIE = {"session_id": "test-session-id"}
VIDEO_FILE = ("video.mp4", io.BytesIO(b"fake video content"), "video/mp4")


# ── Upload ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_video_success_returns_201(client):
    ac, _, _ = client
    resp = await ac.post(
        "/videos/upload",
        data={"title": "My First Video", "description": "A test video"},
        files={"file": VIDEO_FILE},
        cookies=AUTH_COOKIE,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["title"] == "My First Video"
    assert body["data"]["status"] == "uploading"
    assert "id" in body["data"]


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    ac, _, _ = client
    resp = await ac.post(
        "/videos/upload",
        data={"title": "No Auth"},
        files={"file": VIDEO_FILE},
        # no cookies
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_upload_publishes_kafka_event(client):
    ac, _, published = client
    resp = await ac.post(
        "/videos/upload",
        data={"title": "Kafka Test"},
        files={"file": VIDEO_FILE},
        cookies=AUTH_COOKIE,
    )
    assert resp.status_code == 201
    assert len(published) == 1
    event = published[0]
    assert event["topic"] == "video.uploaded"
    assert event["value"]["title"] == "Kafka Test"
    assert event["value"]["creatorId"] == "11111111-1111-1111-1111-111111111111"


# ── Get video ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_video_by_id(client):
    ac, _, _ = client
    # Upload first
    up = await ac.post(
        "/videos/upload",
        data={"title": "Get Me"},
        files={"file": VIDEO_FILE},
        cookies=AUTH_COOKIE,
    )
    video_id = up.json()["data"]["id"]

    resp = await ac.get(f"/videos/{video_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == video_id


@pytest.mark.asyncio
async def test_get_video_not_found_returns_404(client):
    ac, _, _ = client
    resp = await ac.get("/videos/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"] == "VIDEO_NOT_FOUND"


# ── List ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_videos_pagination(client):
    ac, _, _ = client
    for i in range(3):
        await ac.post(
            "/videos/upload",
            data={"title": f"Video {i}"},
            files={"file": VIDEO_FILE},
            cookies=AUTH_COOKIE,
        )
    resp = await ac.get("/videos?page=1&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["total"] == 3


# ── Patch ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_video_as_creator(client):
    ac, _, _ = client
    up = await ac.post(
        "/videos/upload",
        data={"title": "Old Title"},
        files={"file": VIDEO_FILE},
        cookies=AUTH_COOKIE,
    )
    video_id = up.json()["data"]["id"]

    resp = await ac.patch(
        f"/videos/{video_id}",
        json={"title": "New Title"},
        cookies=AUTH_COOKIE,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "New Title"


@pytest.mark.asyncio
async def test_patch_video_as_non_creator_returns_403(client):
    ac, store, _ = client
    # Upload as user 1
    up = await ac.post(
        "/videos/upload",
        data={"title": "Owner Video"},
        files={"file": VIDEO_FILE},
        cookies=AUTH_COOKIE,
    )
    video_id = up.json()["data"]["id"]

    # Inject a different user session
    store["session:other-session"] = "22222222-2222-2222-2222-222222222222"
    resp = await ac.patch(
        f"/videos/{video_id}",
        json={"title": "Hijack"},
        cookies={"session_id": "other-session"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "FORBIDDEN"


# ── Status transitions ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_transitions_uploading_to_processing_to_ready(client):
    ac, _, _ = client
    up = await ac.post(
        "/videos/upload",
        data={"title": "Status Test"},
        files={"file": VIDEO_FILE},
        cookies=AUTH_COOKIE,
    )
    video_id = up.json()["data"]["id"]
    assert up.json()["data"]["status"] == "uploading"

    # processing
    r1 = await ac.patch(
        f"/internal/videos/{video_id}/status",
        json={"status": "processing"},
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["status"] == "processing"

    # ready with HLS + duration
    r2 = await ac.patch(
        f"/internal/videos/{video_id}/status",
        json={"status": "ready", "hls_path": "/media/hls/uuid/index.m3u8", "duration": 125.5},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "ready"
    assert r2.json()["data"]["duration"] == 125.5

    # idempotency — patching ready again must not fail
    r3 = await ac.patch(
        f"/internal/videos/{video_id}/status",
        json={"status": "failed"},
    )
    assert r3.status_code == 200
    assert r3.json()["data"]["status"] == "ready"  # unchanged — already terminal

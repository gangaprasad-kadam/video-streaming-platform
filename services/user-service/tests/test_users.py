"""
Tests for GET /users/me.
"""
import pytest


async def _register_and_login(ac, store, username="eve", email="eve@example.com"):
    await ac.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": "password123",
    })
    login_resp = await ac.post("/auth/login", json={
        "email": email,
        "password": "password123",
    })
    return login_resp.cookies["session_id"]


@pytest.mark.asyncio
async def test_get_me_authenticated(client):
    ac, store = client
    session_id = await _register_and_login(ac, store)

    resp = await ac.get("/users/me", cookies={"session_id": session_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["username"] == "eve"
    assert body["data"]["email"] == "eve@example.com"
    assert "id" in body["data"]
    assert "created_at" in body["data"]


@pytest.mark.asyncio
async def test_get_me_unauthenticated_returns_401(client):
    ac, _ = client
    resp = await ac.get("/users/me")
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_session_expires_returns_401(client):
    ac, store = client
    session_id = await _register_and_login(ac, store)

    # manually remove session from Redis mock
    store.pop(f"session:{session_id}", None)

    resp = await ac.get("/users/me", cookies={"session_id": session_id})
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"

"""
Tests for POST /auth/register, POST /auth/login, POST /auth/logout.
"""
import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    ac, _ = client
    resp = await ac.post("/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "securepassword",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["username"] == "alice"
    assert body["data"]["email"] == "alice@example.com"
    assert "id" in body["data"]


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    ac, _ = client
    payload = {"username": "alice", "email": "alice@example.com", "password": "securepassword"}
    await ac.post("/auth/register", json=payload)
    # second registration with same email
    resp = await ac.post("/auth/register", json={**payload, "username": "alice2"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_duplicate_username_returns_409(client):
    ac, _ = client
    payload = {"username": "alice", "email": "alice@example.com", "password": "securepassword"}
    await ac.post("/auth/register", json=payload)
    resp = await ac.post("/auth/register", json={**payload, "email": "other@example.com"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "CONFLICT"


@pytest.mark.asyncio
async def test_login_success_sets_cookie(client):
    ac, store = client
    await ac.post("/auth/register", json={
        "username": "bob",
        "email": "bob@example.com",
        "password": "mypassword1",
    })
    resp = await ac.post("/auth/login", json={
        "email": "bob@example.com",
        "password": "mypassword1",
    })
    assert resp.status_code == 200
    assert "session_id" in resp.cookies
    # session should exist in Redis mock store
    session_id = resp.cookies["session_id"]
    assert store.get(f"session:{session_id}") is not None


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    ac, _ = client
    await ac.post("/auth/register", json={
        "username": "carol",
        "email": "carol@example.com",
        "password": "rightpassword",
    })
    resp = await ac.post("/auth/login", json={
        "email": "carol@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client):
    ac, _ = client
    resp = await ac.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "password123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_destroys_session(client):
    ac, store = client
    await ac.post("/auth/register", json={
        "username": "dave",
        "email": "dave@example.com",
        "password": "password123",
    })
    login_resp = await ac.post("/auth/login", json={
        "email": "dave@example.com",
        "password": "password123",
    })
    session_id = login_resp.cookies["session_id"]
    assert store.get(f"session:{session_id}") is not None

    logout_resp = await ac.post(
        "/auth/logout", cookies={"session_id": session_id}
    )
    assert logout_resp.status_code == 200
    assert store.get(f"session:{session_id}") is None

"""Watchlist 5 케이스."""
import pytest


async def _register(client, email="w@test.com") -> str:
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "pw12345678", "name": "w"
    })
    return r.json()["token"]


@pytest.mark.asyncio
async def test_empty_list(client):
    token = await _register(client, "a@w.com")
    r = await client.get("/api/watchlist/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_add(client):
    token = await _register(client, "b@w.com")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/watchlist/", json={"ticker": "005930"}, headers=h)
    assert r.status_code == 200
    r = await client.get("/api/watchlist/", headers=h)
    assert len(r.json()) == 1
    assert r.json()[0]["ticker"] == "005930"


@pytest.mark.asyncio
async def test_duplicate(client):
    token = await _register(client, "c@w.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post("/api/watchlist/", json={"ticker": "005930"}, headers=h)
    r = await client.post("/api/watchlist/", json={"ticker": "005930"}, headers=h)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_remove(client):
    token = await _register(client, "d@w.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post("/api/watchlist/", json={"ticker": "005930"}, headers=h)
    r = await client.delete("/api/watchlist/005930", headers=h)
    assert r.status_code == 200
    r = await client.get("/api/watchlist/", headers=h)
    assert r.json() == []


@pytest.mark.asyncio
async def test_remove_not_found(client):
    token = await _register(client, "e@w.com")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.delete("/api/watchlist/999999", headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated(client):
    r = await client.get("/api/watchlist/")
    assert r.status_code == 401

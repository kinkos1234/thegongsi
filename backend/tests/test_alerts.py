import pytest


async def _register(client, email) -> str:
    r = await client.post("/api/auth/register", json={"email": email, "password": "pw12345678", "name": "a"})
    return r.json()["token"]


@pytest.mark.asyncio
async def test_empty(client):
    t = await _register(client, "a1@al.com")
    r = await client.get("/api/alerts/", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create(client):
    t = await _register(client, "a2@al.com")
    h = {"Authorization": f"Bearer {t}"}
    r = await client.post("/api/alerts/", json={
        "channel": "discord",
        "channel_target": "https://discord.com/api/webhooks/1234567890/abcdef",
        "severity_threshold": "high",
    }, headers=h)
    assert r.status_code == 200
    assert "id" in r.json()
    r = await client.get("/api/alerts/", headers=h)
    assert len(r.json()) == 1
    assert r.json()[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_history_empty(client):
    t = await _register(client, "a3@al.com")
    r = await client.get("/api/alerts/history", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_unauthenticated(client):
    r = await client.get("/api/alerts/")
    assert r.status_code == 401

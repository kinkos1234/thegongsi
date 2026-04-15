import pytest


async def _token(client, email="qa@t.com"):
    r = await client.post("/api/auth/register", json={"email": email, "password": "pw12345678", "name": "q"})
    return r.json()["token"]


@pytest.mark.asyncio
async def test_qa_unauthenticated(client):
    r = await client.post("/api/qa/ask", json={"question": "hello"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_qa_blocked_without_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "")
    t = await _token(client, "q1@t.com")
    r = await client.post(
        "/api/qa/ask",
        json={"question": "hello world"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_qa_missing_question(client):
    t = await _token(client, "q2@t.com")
    r = await client.post(
        "/api/qa/ask",
        json={},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert r.status_code == 422

import pytest


@pytest.mark.asyncio
async def test_qa_blocked_without_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "")
    r = await client.post("/api/qa/ask", json={"question": "hi"})
    # no api key → RuntimeError → 503
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_qa_missing_question(client):
    r = await client.post("/api/qa/ask", json={})
    assert r.status_code == 422  # pydantic validation

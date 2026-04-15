import pytest


@pytest.mark.asyncio
async def test_anonymous_disclosure_feedback(client):
    r = await client.post("/api/feedback/disclosure", json={
        "rcept_no": "20260415000001", "rating": 1
    })
    assert r.status_code == 200
    assert r.json() == {"status": "recorded"}


@pytest.mark.asyncio
async def test_memo_feedback_rating_bounds(client):
    r = await client.post("/api/feedback/memo", json={
        "memo_version_id": "abc123", "rating": 5
    })
    assert r.status_code == 422  # ge=-1, le=1 validation


@pytest.mark.asyncio
async def test_memo_feedback_valid(client):
    r = await client.post("/api/feedback/memo", json={
        "memo_version_id": "abc123", "rating": -1, "reason": "부정확한 요약"
    })
    assert r.status_code == 200

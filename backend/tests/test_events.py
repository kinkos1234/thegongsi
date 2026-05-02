import pytest

from app.database import async_session
from app.models.tables import Company, Disclosure


async def _token(client, email="events@t.com"):
    r = await client.post("/api/auth/register", json={"email": email, "password": "pw12345678", "name": "e"})
    return r.json()["token"]


async def _seed_event():
    async with async_session() as db:
        db.add(Company(ticker="005930", corp_code="00126380", name_ko="삼성전자", market="KOSPI"))
        db.add(
            Disclosure(
                rcept_no="20260430009999",
                corp_code="00126380",
                ticker="005930",
                report_nm="주요사항보고서",
                rcept_dt="2026-04-30",
                anomaly_severity="high",
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_event_review_requires_auth(client):
    await _seed_event()
    r = await client.post(
        "/api/events/reviews",
        json={"rcept_no": "20260430009999", "status": "reviewed"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_event_review_reflected_in_inbox(client):
    await _seed_event()
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/events/reviews",
        json={"rcept_no": "20260430009999", "status": "escalated", "note": "PM 확인 필요"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["review"]["review_status"] == "escalated"
    assert r.json()["review"]["note"] == "PM 확인 필요"

    r = await client.get("/api/stats/event-inbox?days=7&limit=10", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["status"] == "escalated"
    assert body["items"][0]["review_note"] == "PM 확인 필요"
    assert body["counts"]["new"] == 0
    assert body["counts"]["escalated"] == 1


@pytest.mark.asyncio
async def test_event_review_summary_and_csv_export(client):
    await _seed_event()
    token = await _token(client, "events-export@t.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/events/reviews",
        json={"rcept_no": "20260430009999", "status": "reviewed", "note": "확인 완료"},
        headers=headers,
    )

    r = await client.get("/api/events/reviews/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["reviewed"] == 1
    assert r.json()["total"] == 1

    r = await client.get("/api/events/reviews/export.csv", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "20260430009999" in r.text
    assert "확인 완료" in r.text

"""Watchlist 5 케이스."""
import pytest

from app.database import async_session
from app.models.tables import Company, Disclosure


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


@pytest.mark.asyncio
async def test_watchlist_brief_filters_to_user_tickers(client):
    token = await _register(client, "brief@w.com")
    h = {"Authorization": f"Bearer {token}"}
    async with async_session() as db:
        db.add(Company(ticker="005930", corp_code="00126380", name_ko="삼성전자", market="KOSPI"))
        db.add(Company(ticker="000660", corp_code="00164779", name_ko="SK하이닉스", market="KOSPI"))
        db.add(
            Disclosure(
                rcept_no="20260430005555",
                corp_code="00126380",
                ticker="005930",
                report_nm="주요사항보고서(유상증자결정)",
                rcept_dt="2026-04-30",
                anomaly_severity="high",
                anomaly_reason="희석 가능성 확인 필요",
            )
        )
        db.add(
            Disclosure(
                rcept_no="20260430006666",
                corp_code="00164779",
                ticker="000660",
                report_nm="주요사항보고서(합병결정)",
                rcept_dt="2026-04-30",
                anomaly_severity="med",
            )
        )
        await db.commit()

    await client.post("/api/watchlist/", json={"ticker": "005930", "backfill_days": 0}, headers=h)
    r = await client.get("/api/watchlist/brief?days=7", headers=h)

    assert r.status_code == 200
    body = r.json()
    assert body["watchlist_count"] == 1
    assert body["counts"]["high"] == 1
    assert body["counts"]["med"] == 0
    assert len(body["items"]) == 1
    assert body["items"][0]["ticker"] == "005930"
    assert body["items"][0]["reason"] == "희석 가능성 확인 필요"

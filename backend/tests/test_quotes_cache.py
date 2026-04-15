"""quotes 캐시 동작 테스트 (yfinance 실제 호출은 mock)."""
import pytest

from app.services import quotes


@pytest.mark.asyncio
async def test_cache_hit(monkeypatch):
    quotes._cache.clear()

    calls = {"n": 0}
    def fake_fetch(ticker):
        calls["n"] += 1
        return {"ticker": ticker, "price": 70000, "change_percent": 1.0, "series": []}

    monkeypatch.setattr(quotes, "_fetch_sync", fake_fetch)

    r1 = await quotes.get_quote("005930")
    r2 = await quotes.get_quote("005930")
    assert r1["cached"] is False
    assert r2["cached"] is True
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_force_refresh(monkeypatch):
    quotes._cache.clear()

    calls = {"n": 0}
    def fake_fetch(ticker):
        calls["n"] += 1
        return {"ticker": ticker, "price": 70000, "change_percent": 1.0, "series": []}

    monkeypatch.setattr(quotes, "_fetch_sync", fake_fetch)
    await quotes.get_quote("005930")
    await quotes.get_quote("005930", force=True)
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_stale_fallback_on_error(monkeypatch):
    quotes._cache.clear()

    def ok_fetch(ticker):
        return {"ticker": ticker, "price": 70000, "change_percent": 1.0, "series": []}

    def fail_fetch(ticker):
        raise RuntimeError("network")

    # 1차 성공으로 캐시 채움
    monkeypatch.setattr(quotes, "_fetch_sync", ok_fetch)
    await quotes.get_quote("005930")

    # TTL 만료 흉내 → 실패하면 stale 반환
    monkeypatch.setattr(quotes, "_fetch_sync", fail_fetch)
    quotes._cache["005930"] = (0.0, quotes._cache["005930"][1])  # 오래 전으로
    r = await quotes.get_quote("005930")
    assert r.get("stale") is True

"""KRX 재무비율·공매도 수집 (pykrx).

일일 스냅샷. 증분은 단순 (ticker, date) 중복 체크.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.tables import FinancialSnapshot, ShortSellingSnapshot

logger = logging.getLogger(__name__)


def _fetch_fundamentals_sync(date: str, market: str) -> list[dict]:
    from pykrx import stock
    df = stock.get_market_fundamental_by_ticker(date, market=market)
    caps = stock.get_market_cap_by_ticker(date, market=market)
    rows = []
    for ticker, r in df.iterrows():
        cap = int(caps.loc[ticker, "시가총액"]) // 100_000_000 if ticker in caps.index else None
        rows.append({
            "ticker": ticker,
            "date": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
            "per": float(r["PER"]) if r["PER"] > 0 else None,
            "pbr": float(r["PBR"]) if r["PBR"] > 0 else None,
            "eps": float(r["EPS"]) if r["EPS"] else None,
            "bps": float(r["BPS"]) if r["BPS"] else None,
            "dividend_yield": float(r["DIV"]) if r["DIV"] else None,
            "market_cap": cap,
        })
    return rows


def _fetch_short_sync(date: str, market: str) -> list[dict]:
    from pykrx import stock
    try:
        df = stock.get_shorting_status_by_ticker(date, market=market)
    except Exception:
        return []
    rows = []
    for ticker, r in df.iterrows():
        rows.append({
            "ticker": ticker,
            "date": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
            "volume": int(r.get("공매도", 0) or 0),
            "value": int(r.get("공매도거래대금", 0) or 0),
            "ratio": float(r.get("공매도비중", 0) or 0),
        })
    return rows


async def fetch_fundamentals(tickers: list[str] | None = None) -> dict:
    """KOSPI 일일 fundamental + short. tickers=None이면 전수, 지정 시 필터."""
    date = datetime.now().strftime("%Y%m%d")
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=2) as executor:
        fund_fut = loop.run_in_executor(executor, _fetch_fundamentals_sync, date, "KOSPI")
        short_fut = loop.run_in_executor(executor, _fetch_short_sync, date, "KOSPI")
        fundamentals, shorts = await asyncio.gather(fund_fut, short_fut, return_exceptions=True)
    if isinstance(fundamentals, Exception):
        logger.exception("fundamentals fetch failed")
        fundamentals = []
    if isinstance(shorts, Exception):
        logger.exception("shorts fetch failed")
        shorts = []

    if tickers:
        tset = set(tickers)
        fundamentals = [r for r in fundamentals if r["ticker"] in tset]
        shorts = [r for r in shorts if r["ticker"] in tset]

    inserted_f = 0
    inserted_s = 0
    async with async_session() as db:
        for row in fundamentals:
            if await _exists(db, FinancialSnapshot, row["ticker"], row["date"]):
                continue
            db.add(FinancialSnapshot(**row))
            inserted_f += 1
        for row in shorts:
            if await _exists(db, ShortSellingSnapshot, row["ticker"], row["date"]):
                continue
            db.add(ShortSellingSnapshot(**row))
            inserted_s += 1
        await db.commit()

    logger.info(f"Fundamentals: {inserted_f} inserted, shorts: {inserted_s} inserted")
    return {"fundamentals": inserted_f, "shorts": inserted_s, "date": date}


async def _exists(db: AsyncSession, model, ticker: str, date: str) -> bool:
    result = await db.execute(
        select(model).where(model.ticker == ticker, model.date == date).limit(1)
    )
    return result.scalar_one_or_none() is not None

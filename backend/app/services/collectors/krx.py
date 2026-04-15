"""KRX 시세 수집기. stock-strategy/korean_market.py 패턴 계승.

KOSPI 200 전체로 확장 예정. 현재는 주요 10종목 샘플.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

logger = logging.getLogger(__name__)

SAMPLE_TICKERS = [
    ("005930.KS", "삼성전자", "KOSPI"),
    ("000660.KS", "SK하이닉스", "KOSPI"),
    ("373220.KS", "LG에너지솔루션", "KOSPI"),
    ("005380.KS", "현대자동차", "KOSPI"),
    ("035420.KS", "NAVER", "KOSPI"),
    ("000270.KS", "기아", "KOSPI"),
    ("068270.KS", "셀트리온", "KOSPI"),
    ("035720.KS", "카카오", "KOSPI"),
    ("051910.KS", "LG화학", "KOSPI"),
    ("006400.KS", "삼성SDI", "KOSPI"),
]


def _fetch(ticker: str, name: str, market: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        prev = getattr(info, "previous_close", None)
        if price is None:
            return None
        change_pct = round((price - prev) / prev * 100, 2) if prev else None
        return {
            "ticker": ticker.split(".")[0],
            "name": name,
            "market": market,
            "price": round(price, 2),
            "change_percent": change_pct,
        }
    except Exception as e:
        logger.error(f"{ticker}: {e}")
        return None


async def fetch_kospi_quotes() -> dict:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [loop.run_in_executor(executor, _fetch, tk, n, m) for tk, n, m in SAMPLE_TICKERS]
        results = await asyncio.gather(*futures, return_exceptions=True)
    rows = [r for r in results if isinstance(r, dict)]
    logger.info(f"KRX: {len(rows)}/{len(SAMPLE_TICKERS)} fetched")
    return {"count": len(rows), "rows": rows}

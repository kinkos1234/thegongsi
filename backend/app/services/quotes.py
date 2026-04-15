"""시세 조회 + 15분 TTL 인메모리 캐시.

yfinance는 비공식 스크레이퍼 — rate limit 회피를 위해 캐시 필수.
Phase 2: Redis로 이관 + 프로세스 간 공유.
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

TTL_SECONDS = 15 * 60
_cache: dict[str, tuple[float, dict]] = {}
_executor = ThreadPoolExecutor(max_workers=4)


def _fetch_sync(ticker: str) -> dict:
    """yfinance로 현재가 + 60일 종가."""
    import yfinance as yf
    yf_ticker = ticker if "." in ticker else f"{ticker}.KS"
    t = yf.Ticker(yf_ticker)
    hist = t.history(period="3mo")
    if hist.empty:
        # 코스닥 fallback
        t = yf.Ticker(f"{ticker}.KQ")
        hist = t.history(period="3mo")
    if hist.empty:
        return {"ticker": ticker, "price": None, "change_percent": None, "series": []}

    closes = hist["Close"].tolist()
    dates = [d.strftime("%Y-%m-%d") for d in hist.index]
    series = [{"d": d, "c": round(float(c), 2)} for d, c in zip(dates, closes)][-60:]

    price = round(float(closes[-1]), 2)
    change_percent = None
    if len(closes) >= 2 and closes[-2] > 0:
        change_percent = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)

    return {"ticker": ticker, "price": price, "change_percent": change_percent, "series": series}


async def get_quote(ticker: str, force: bool = False) -> dict:
    """캐시 first, 만료 시 fetch. force=True → TTL 무시."""
    now = time.time()
    entry = _cache.get(ticker)
    if entry and not force:
        ts, data = entry
        if now - ts < TTL_SECONDS:
            return {**data, "cached": True, "age_sec": int(now - ts)}

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(_executor, _fetch_sync, ticker)
    except Exception as e:
        logger.exception(f"quote fetch failed {ticker}")
        # 캐시 있으면 stale이라도 반환
        if entry:
            return {**entry[1], "cached": True, "stale": True, "error": str(e)}
        raise
    _cache[ticker] = (now, data)
    return {**data, "cached": False, "age_sec": 0}

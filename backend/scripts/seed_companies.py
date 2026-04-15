"""KOSPI/KOSDAQ 상장사 기본 정보 seed (pykrx 기반).

DART 키 없어도 동작. ticker + name_ko + market 채움.
corp_code는 DART 키 확보 후 별도 스크립트로 보강.

사용법:
    python scripts/seed_companies.py            # KOSPI 전체
    python scripts/seed_companies.py --kosdaq   # KOSDAQ 추가
    python scripts/seed_companies.py --top 200  # KOSPI 200만
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.database import init_db, async_session
from app.models.tables import Company

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _fetch_listing(market: str, top: int | None) -> list[tuple[str, str]]:
    """pykrx로 시장 종목 리스트 반환. [(ticker, name), ...]"""
    from pykrx import stock
    today = datetime.now().strftime("%Y%m%d")
    tickers = stock.get_market_ticker_list(today, market=market)
    if top:
        # 시총 상위 top
        caps = stock.get_market_cap_by_ticker(today, market=market)
        caps = caps.sort_values("시가총액", ascending=False).head(top)
        tickers = list(caps.index)
    return [(t, stock.get_market_ticker_name(t)) for t in tickers]


async def seed(include_kosdaq: bool, top: int | None):
    await init_db()

    rows: list[tuple[str, str, str]] = []
    for market_code, market_label in [("KOSPI", "KOSPI"), ("KOSDAQ", "KOSDAQ")]:
        if market_code == "KOSDAQ" and not include_kosdaq:
            continue
        items = _fetch_listing(market_code, top)
        rows.extend((t, n, market_label) for t, n in items)
        logger.info(f"{market_label}: {len(items)} tickers")

    inserted = 0
    async with async_session() as db:
        for ticker, name, market in rows:
            existing = await db.execute(select(Company).where(Company.ticker == ticker))
            c = existing.scalar_one_or_none()
            if c:
                c.name_ko = name
                c.market = market
            else:
                db.add(Company(
                    ticker=ticker,
                    corp_code="",  # DART 키 확보 후 보강
                    name_ko=name,
                    market=market,
                ))
                inserted += 1
        await db.commit()
    logger.info(f"DB: {inserted} inserted, {len(rows) - inserted} updated")


if __name__ == "__main__":
    include_kosdaq = "--kosdaq" in sys.argv
    top = None
    if "--top" in sys.argv:
        top = int(sys.argv[sys.argv.index("--top") + 1])
    asyncio.run(seed(include_kosdaq, top))

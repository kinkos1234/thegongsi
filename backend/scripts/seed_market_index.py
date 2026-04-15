"""KOSPI 200 + KOSDAQ 150 + 섹터별 대표 기업을 Company 테이블에 seed.

Usage:
    python scripts/seed_market_index.py                # KOSPI 200 + KOSDAQ 150
    python scripts/seed_market_index.py --kospi-only
    python scripts/seed_market_index.py --sector-rep 5 # 섹터별 시총 상위 5개만

pykrx 인덱스 코드:
- 1028 = KOSPI 200
- 2203 = KOSDAQ 150

dart-fss corp_list로 corp_code + market/sector 자동 매칭.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed-market")


def _fetch_index_tickers(index_code: str) -> list[str]:
    """pykrx로 인덱스 구성 종목 리스트."""
    from pykrx import stock
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    try:
        tickers = stock.get_index_portfolio_deposit_file(index_code, today)
    except Exception:
        # fallback: 최근 영업일
        tickers = stock.get_index_portfolio_deposit_file(index_code)
    return list(tickers)


def _fetch_sector_top(market: str, top_per_sector: int) -> list[str]:
    """pykrx 시총 상위로 sector 대체 (pykrx에 직접 sector API 없음)."""
    from pykrx import stock
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    caps = stock.get_market_cap_by_ticker(today, market=market)
    caps = caps.sort_values("시가총액", ascending=False).head(top_per_sector * 20)
    return list(caps.index)


async def seed(kospi: bool, kosdaq: bool, sector_rep: int):
    from sqlalchemy import select
    from app.database import init_db, async_session
    from app.models.tables import Company
    from app.services.collectors.dart import _get_corp_list

    await init_db()

    all_tickers: set[str] = set()
    if kospi:
        t = _fetch_index_tickers("1028")
        logger.info(f"KOSPI 200: {len(t)} tickers")
        all_tickers.update(t)
    if kosdaq:
        t = _fetch_index_tickers("2203")
        logger.info(f"KOSDAQ 150: {len(t)} tickers")
        all_tickers.update(t)
    if sector_rep > 0:
        # pykrx에 sector API 부재 — 시총 상위로 대체 커버리지
        t = _fetch_sector_top("KOSPI", sector_rep) + _fetch_sector_top("KOSDAQ", sector_rep)
        logger.info(f"Market cap top ({sector_rep}×20): {len(t)} tickers")
        all_tickers.update(t)

    # DART corp_list 매칭
    corp_list = _get_corp_list()
    corp_by_stock = {c.stock_code: c for c in corp_list if getattr(c, "stock_code", None)}

    inserted = 0
    updated = 0
    skipped = 0
    async with async_session() as db:
        for ticker in all_tickers:
            corp = corp_by_stock.get(ticker)
            if not corp:
                skipped += 1
                continue
            market = "KOSPI" if getattr(corp, "corp_cls", "Y") == "Y" else "KOSDAQ"
            existing = await db.execute(select(Company).where(Company.ticker == ticker))
            c = existing.scalar_one_or_none()
            if c:
                c.name_ko = corp.corp_name
                c.corp_code = corp.corp_code
                c.market = market
                if not c.sector and getattr(corp, "sector", None):
                    c.sector = corp.sector
                updated += 1
            else:
                db.add(Company(
                    ticker=ticker,
                    corp_code=corp.corp_code,
                    name_ko=corp.corp_name,
                    market=market,
                    sector=getattr(corp, "sector", None),
                ))
                inserted += 1
        await db.commit()

    logger.info(f"Done: {inserted} inserted, {updated} updated, {skipped} skipped (DART 미등록 ETF/리츠 등)")
    logger.info(f"Total Company rows target: ~{len(all_tickers) - skipped}")

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


if __name__ == "__main__":
    kospi = "--kosdaq-only" not in sys.argv
    kosdaq = "--kospi-only" not in sys.argv
    sector_rep = 0
    if "--sector-rep" in sys.argv:
        sector_rep = int(sys.argv[sys.argv.index("--sector-rep") + 1])
    asyncio.run(seed(kospi=kospi, kosdaq=kosdaq, sector_rep=sector_rep))

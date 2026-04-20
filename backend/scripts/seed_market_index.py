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
    """실제 인덱스 구성원 조회. 1028=KOSPI 200, 2203=KOSDAQ 150.

    pykrx `get_index_portfolio_deposit_file`가 KRX OTP 실패 시 시총 상위로 fallback.
    둘 다 실패하면 [] 반환. DART corpCode XML fallback은 512MB Fly VM에서 OOM
    위험이라 의도적으로 제외 (weekly_sync는 target=0이면 seed 호출 skip).
    """
    from pykrx import stock
    from datetime import datetime, timedelta
    for i in range(1, 8):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            tickers = stock.get_index_portfolio_deposit_file(index_code, d)
            if tickers:
                return list(tickers)
        except Exception:
            continue
    logger.warning(f"pykrx 인덱스 {index_code} 조회 실패 — 시총 상위로 fallback")
    if index_code == "1028":
        return _fetch_top_by_market_cap("KOSPI", 200)
    if index_code == "2203":
        return _fetch_top_by_market_cap("KOSDAQ", 150)
    return []


def _fetch_top_by_market_cap(market: str, top: int) -> list[str]:
    """KOSPI/KOSDAQ 시총 상위 N 종목. pykrx 실패 시 DART corp_list로 fallback.

    pykrx는 KRX OTP/크롤링 기반이라 종종 실패 — DART는 API이라 안정적.
    """
    from pykrx import stock
    from datetime import datetime, timedelta
    for i in range(1, 8):  # 어제부터 최대 7일 과거
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            caps = stock.get_market_cap_by_ticker(d, market=market)
            if caps is not None and not caps.empty:
                caps = caps.sort_values("시가총액", ascending=False).head(top)
                return list(caps.index)
        except Exception:
            continue
    return []


def _fetch_from_dart_corp_list(market_cls: str, top: int) -> list[str]:
    """DART corp_list 기반 fallback. market_cls: 'Y'=KOSPI, 'K'=KOSDAQ.

    시총 정보 없어 단순 상장사 상위 top개 (수기 정렬 불가) — 시총 랭킹 대신
    전체 커버리지 샘플. pykrx 실패 시 대안.
    """
    from app.services.collectors.dart import _get_corp_list
    corp_list = _get_corp_list()
    filtered = [
        c for c in corp_list
        if getattr(c, "corp_cls", "") == market_cls
        and getattr(c, "stock_code", None)
    ]
    # corp_code 기준 정렬 (시총 정보 없음) → 상위 top개
    filtered.sort(key=lambda c: c.corp_code)
    return [c.stock_code for c in filtered[:top]]


async def seed(kospi: bool, kosdaq: bool, sector_rep: int):
    from sqlalchemy import select
    from app.database import init_db, async_session
    from app.models.tables import Company
    from app.services.collectors.dart import _get_corp_list

    await init_db()

    all_tickers: set[str] = set()
    if kospi:
        t = _fetch_top_by_market_cap("KOSPI", 200)
        if not t:
            logger.warning("pykrx KOSPI 실패 — DART corp_list fallback")
            t = _fetch_from_dart_corp_list("Y", 300)
        logger.info(f"KOSPI: {len(t)} tickers")
        all_tickers.update(t)
    if kosdaq:
        t = _fetch_top_by_market_cap("KOSDAQ", 150)
        if not t:
            logger.warning("pykrx KOSDAQ 실패 — DART corp_list fallback")
            t = _fetch_from_dart_corp_list("K", 300)
        logger.info(f"KOSDAQ: {len(t)} tickers")
        all_tickers.update(t)
    if sector_rep > 0:
        # 추가 커버리지: 각 시장 시총 상위 N*20 (섹터 분산)
        t = _fetch_top_by_market_cap("KOSPI", sector_rep * 20) + _fetch_top_by_market_cap(
            "KOSDAQ", sector_rep * 20
        )
        logger.info(f"Sector-rep extended: +{len(t)} tickers")
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

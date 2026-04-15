"""주간 시장 인덱스 sync + 신규 상장 종목 감지.

Usage:
    # 크론: 매주 월요일 KST 07:00
    0 22 * * 0 /path/to/.venv/bin/python /path/to/scripts/weekly_sync.py

동작:
1. KOSPI 200 + KOSDAQ 150 최신 구성원 조회 (pykrx)
2. 기존 Company 테이블 기준 diff:
   - 신규 편입: Company row 생성 + (선택) 90일 backfill 큐
   - 편출: 플래그 (삭제 안 함, 과거 데이터 유지)
3. 결과 로그 + optional 알림

scheduler.py가 항상 실행 중이면 APScheduler에 추가, 아니면 cron.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("weekly-sync")


async def weekly_sync(auto_backfill: bool = False):
    from sqlalchemy import select
    from app.database import async_session
    from app.models.tables import Company
    from scripts.seed_market_index import _fetch_index_tickers

    kospi = set(_fetch_index_tickers("1028"))
    kosdaq = set(_fetch_index_tickers("2203"))
    target = kospi | kosdaq
    logger.info(f"Index constituents target: KOSPI 200 {len(kospi)}, KOSDAQ 150 {len(kosdaq)}, union {len(target)}")

    async with async_session() as db:
        existing_tickers = {
            r[0] for r in (await db.execute(select(Company.ticker))).all()
        }

    new_tickers = target - existing_tickers
    missing_tickers = existing_tickers - target  # 편출 후보

    logger.info(f"New: {len(new_tickers)}, Missing (편출 후보): {len(missing_tickers)}")

    if new_tickers:
        # Company row + corp_code 부트스트랩 (seed_market_index 재사용)
        from scripts.seed_market_index import seed
        await seed(kospi=True, kosdaq=True, sector_rep=0)
        logger.info(f"Seeded new companies: {list(new_tickers)[:10]}...")

    if auto_backfill and new_tickers:
        from app.services.collectors.dart import backfill_ticker
        for t in new_tickers:
            try:
                r = await backfill_ticker(t, days=90)
                logger.info(f"backfill {t}: {r.get('inserted', 0)} new disclosures")
            except Exception as e:
                logger.warning(f"backfill {t} failed: {e}")

    return {"new": list(new_tickers), "missing": list(missing_tickers)}


if __name__ == "__main__":
    auto_backfill = "--backfill" in sys.argv
    result = asyncio.run(weekly_sync(auto_backfill=auto_backfill))
    print(f"Summary: {len(result['new'])} new, {len(result['missing'])} missing")

"""권리락/배당락 이벤트 초기 스캔.

Companies 테이블에서 corp_code 있는 종목 전체를 순회하며
OpenDART 주요사항보고서 4종(유상/무상증자, 주식/현금배당)에서 날짜 이벤트 추출.

사용:
    python scripts/scan_ex_dates.py                     # 전체
    python scripts/scan_ex_dates.py --days 60           # 기간 조정
    python scripts/scan_ex_dates.py --limit 100         # 종목 수 제한 (테스트)
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _to_asyncpg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgresql://", 1)
    return url


async def run(days: int, limit: int | None):
    from app.services.calendar.ex_dates import scan_ex_dates, upsert_events

    db_url = _to_asyncpg_dsn(os.environ.get("DATABASE_URL", ""))
    if not db_url.startswith("postgres"):
        logger.error("Postgres DB URL 필요"); sys.exit(1)

    import asyncpg
    conn = await asyncpg.connect(db_url)
    try:
        q = "SELECT ticker, corp_code FROM companies WHERE corp_code IS NOT NULL AND corp_code <> '' "
        q += "AND market IN ('KOSPI', 'KOSDAQ') ORDER BY ticker"
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = await conn.fetch(q)
        tickers = [(r["ticker"], r["corp_code"]) for r in rows]
        logger.info(f"스캔 대상: {len(tickers)} 종목 × 4 endpoints × {days}일")

        # 100개씩 chunk — 한 번에 4000개 × 4 = 16,000 request는 DART 10,000/day 초과
        chunk = 50
        total_events = 0
        for i in range(0, len(tickers), chunk):
            sub = tickers[i : i + chunk]
            events = await scan_ex_dates(sub, days_back=days)
            written = await upsert_events(conn, events)
            total_events += written
            logger.info(f"  {i + len(sub)}/{len(tickers)} → +{written} events (누적 {total_events})")
        logger.info(f"완료: 총 {total_events} events upserted")
    finally:
        await conn.close()


if __name__ == "__main__":
    days = 60
    limit: int | None = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(run(days, limit))

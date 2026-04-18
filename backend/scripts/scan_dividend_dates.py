"""배당 ex-date 백필 스크립트.

disclosures 테이블에서 배당결정 패턴 매치 → document.xml 파싱 → calendar_events upsert.

사용:
    python scripts/scan_dividend_dates.py                 # 최근 180일 전체
    python scripts/scan_dividend_dates.py --days 365      # 기간 확장
    python scripts/scan_dividend_dates.py --limit 50      # 테스트 (건수 제한)
"""
import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts._logging_setup import setup_script_logging
setup_script_logging()
logger = logging.getLogger(__name__)


def _to_asyncpg_dsn(url: str) -> str:
    for p in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(p):
            return url.replace(p, "postgresql://", 1)
    return url


async def run(days: int, limit: int | None):
    from app.services.calendar.dividend_dates import scan_dividends_by_rcept
    from app.services.calendar.ex_dates import upsert_events

    db_url = _to_asyncpg_dsn(os.environ.get("DATABASE_URL", ""))
    if not db_url.startswith("postgres"):
        logger.error("Postgres DB URL 필요"); sys.exit(1)

    since = (date.today() - timedelta(days=days)).isoformat()
    # 배당결정 패턴 (현금·현물·주식) — 앞뒤 공백/정정 태그 모두 포함
    pattern = "%배당결정%"

    import asyncpg
    conn = await asyncpg.connect(db_url)
    try:
        q = """
        SELECT ticker, rcept_no, report_nm
        FROM disclosures
        WHERE rcept_dt >= $1 AND report_nm LIKE $2
        ORDER BY rcept_dt DESC
        """
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = await conn.fetch(q, since, pattern)
        filings = [(r["ticker"], r["rcept_no"], r["report_nm"]) for r in rows]
        logger.info(f"배당결정 공시 {len(filings)}건 (최근 {days}일)")

        if not filings:
            logger.info("대상 공시 없음 — 종료")
            return

        chunk = 30
        total = 0
        for i in range(0, len(filings), chunk):
            sub = filings[i : i + chunk]
            events = await scan_dividends_by_rcept(sub, concurrency=3)
            written = await upsert_events(conn, events)
            total += written
            logger.info(f"  {i + len(sub)}/{len(filings)} → +{written} events (누적 {total})")
        logger.info(f"완료: 총 {total} events upserted")
    finally:
        await conn.close()


if __name__ == "__main__":
    days = 180
    limit: int | None = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(run(days, limit))

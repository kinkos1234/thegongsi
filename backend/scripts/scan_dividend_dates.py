"""배당 ex-date 백필 스크립트.

disclosures 테이블에서 배당결정 패턴 매치 → document.xml 파싱 → calendar_events upsert.

사용:
    python scripts/scan_dividend_dates.py                 # 최근 180일 전체
    python scripts/scan_dividend_dates.py --days 365      # 기간 확장
    python scripts/scan_dividend_dates.py --limit 50      # 테스트 (건수 제한)
"""
import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts._logging_setup import setup_script_logging
setup_script_logging()
logger = logging.getLogger(__name__)


async def run(days: int, limit: int | None):
    from app.services.calendar.dividend_dates import scan_dividends_by_rcept
    from app.models.tables import Disclosure
    from app.database import async_session
    from app.services.calendar.upsert import upsert_calendar_events
    from sqlalchemy import select

    since = (date.today() - timedelta(days=days)).isoformat()
    # 배당결정 패턴 (현금·현물·주식) — 앞뒤 공백/정정 태그 모두 포함
    pattern = "%배당결정%"

    q = (
        select(Disclosure.ticker, Disclosure.rcept_no, Disclosure.report_nm)
        .where(Disclosure.rcept_dt >= since, Disclosure.report_nm.like(pattern))
        .order_by(Disclosure.rcept_dt.desc())
    )
    if limit:
        q = q.limit(limit)

    async with async_session() as session:
        rows = (await session.execute(q)).all()

    filings = [(r.ticker, r.rcept_no, r.report_nm) for r in rows]
    logger.info(f"배당결정 공시 {len(filings)}건 (최근 {days}일)")

    if not filings:
        logger.info("대상 공시 없음 — 종료")
        return

    chunk = 30
    total = 0
    for i in range(0, len(filings), chunk):
        sub = filings[i : i + chunk]
        events = await scan_dividends_by_rcept(sub, concurrency=3)
        written = await upsert_calendar_events(events)
        total += written
        logger.info(f"  {i + len(sub)}/{len(filings)} → +{written} events (누적 {total})")
    logger.info(f"완료: 총 {total} events upserted")


if __name__ == "__main__":
    days = 180
    limit: int | None = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(run(days, limit))

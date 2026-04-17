"""list.json 기반 ex-date 스캐너 v2 실행 스크립트.

vs v1 (종목별 per-endpoint): 7,848 calls → v2: ~10-50 calls.

사용:
    python scripts/scan_ex_dates_v2.py                 # 최근 180일
    python scripts/scan_ex_dates_v2.py --days 14       # 증분 (일일 크론용)
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
    for p in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(p):
            return url.replace(p, "postgresql://", 1)
    return url


async def run(days: int):
    from app.services.calendar.ex_dates_v2 import scan_ex_dates_v2
    from app.services.calendar.ex_dates import upsert_events

    db_url = _to_asyncpg_dsn(os.environ.get("DATABASE_URL", ""))
    if not db_url.startswith("postgres"):
        logger.error("Postgres DB URL 필요"); sys.exit(1)

    events = await scan_ex_dates_v2(days_back=days, concurrency=3)
    logger.info(f"총 {len(events)} events 추출")

    if not events:
        logger.info("저장할 이벤트 없음 — 종료")
        return

    import asyncpg
    conn = await asyncpg.connect(db_url)
    try:
        written = await upsert_events(conn, events)
        logger.info(f"upsert 완료: {written} rows")
    finally:
        await conn.close()


if __name__ == "__main__":
    days = 180
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    asyncio.run(run(days))

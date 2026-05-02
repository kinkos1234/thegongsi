"""list.json 기반 ex-date 스캐너 v2 실행 스크립트.

vs v1 (종목별 per-endpoint): 7,848 calls → v2: ~10-50 calls.

사용:
    python scripts/scan_ex_dates_v2.py                 # 최근 180일
    python scripts/scan_ex_dates_v2.py --days 14       # 증분 (일일 크론용)
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts._logging_setup import setup_script_logging
setup_script_logging()
logger = logging.getLogger(__name__)


async def run(days: int):
    from app.services.calendar.ex_dates_v2 import scan_ex_dates_v2
    from app.services.calendar.upsert import upsert_calendar_events

    events = await scan_ex_dates_v2(days_back=days, concurrency=3)
    logger.info(f"총 {len(events)} events 추출")

    if not events:
        logger.info("저장할 이벤트 없음 — 종료")
        return

    written = await upsert_calendar_events(events)
    logger.info(f"upsert 완료: {written} rows")


if __name__ == "__main__":
    days = 180
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    asyncio.run(run(days))

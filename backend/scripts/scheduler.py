"""데이터 수집 + 알림 스케줄러. stock-strategy 뼈대 이식.

사용법:
    python scripts/scheduler.py              # 매일 KST 06:00 자동 실행
    python scripts/scheduler.py --once       # 즉시 1회 (수집만)
    python scripts/scheduler.py --once --alerts  # 즉시 1회 + 알림 체크
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.database import init_db, async_session
from app.services.data_collector import collect_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_once(check_alerts: bool = False):
    await init_db()
    result = await collect_all()
    logger.info(f"Collection result: {result}")

    if check_alerts:
        from app.services.alert_service import check_and_alert
        async with async_session() as db:
            alert_result = await check_and_alert(db)
            logger.info(f"Alert result: {alert_result}")


def run_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler()

    def daily_job():
        asyncio.run(run_once(check_alerts=True))

    # KST 06:00 = UTC 21:00
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=21, minute=0, timezone="UTC"),
        id="daily_collection",
        name="Daily DART/KRX collection + alerts",
    )

    # 매주 월요일 KST 07:00 = UTC 일요일 22:00 — 인덱스 구성원 sync
    def weekly_index_sync():
        from scripts.weekly_sync import weekly_sync
        asyncio.run(weekly_sync(auto_backfill=True))

    scheduler.add_job(
        weekly_index_sync,
        CronTrigger(day_of_week="sun", hour=22, minute=0, timezone="UTC"),
        id="weekly_index_sync",
        name="Weekly KOSPI 200 + KOSDAQ 150 membership sync + backfill",
    )

    logger.info("Scheduler started. Daily KST 06:00 + Weekly KST Mon 07:00 (index sync).")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    if "--once" in sys.argv:
        asyncio.run(run_once(check_alerts="--alerts" in sys.argv))
    else:
        run_scheduler()

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

    # 매주 토요일 KST 05:00 = UTC 금요일 20:00 — companies seed + market enrichment
    # 신규 상장/폐지/KOSPI↔KOSDAQ 이동 반영.
    def weekly_market_refresh():
        import subprocess
        import os
        env = os.environ.copy()
        # seed_dart_native: 상장사 신규 등록
        subprocess.run(["python", "scripts/seed_dart_native.py"], env=env, check=False)
        # enrich_market: KIND 기준 KOSPI/KOSDAQ 라벨 재적용
        subprocess.run(["python", "scripts/enrich_market.py"], env=env, check=False)

    scheduler.add_job(
        weekly_market_refresh,
        CronTrigger(day_of_week="fri", hour=20, minute=0, timezone="UTC"),
        id="weekly_market_refresh",
        name="Weekly companies seed + KIND market enrichment",
    )

    # 매일 KST 07:30 = UTC 22:30 — 당일 배당 ex-date 증분 스캔 (소량, 쓰레드 피드백 대응)
    def daily_dividend_scan():
        import subprocess
        import os
        subprocess.run(
            ["python", "scripts/scan_dividend_dates.py", "--days", "14"],
            env=os.environ.copy(), check=False,
        )

    scheduler.add_job(
        daily_dividend_scan,
        CronTrigger(hour=22, minute=30, timezone="UTC"),
        id="daily_dividend_scan",
        name="Daily dividend ex-date incremental scan (last 14d)",
    )

    logger.info(
        "Scheduler: Daily 06:00 collect + 07:30 dividend scan; Mon 07:00 index sync; Sat 05:00 market refresh (KST)."
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    if "--once" in sys.argv:
        asyncio.run(run_once(check_alerts="--alerts" in sys.argv))
    else:
        run_scheduler()

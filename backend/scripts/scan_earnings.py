"""실적 공정공시 수집 스크립트.

사용:
    python scripts/scan_earnings.py --days 30
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


async def main():
    from app.services.collectors.earnings import collect_earnings
    days = 14
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    result = await collect_earnings(days_back=days)
    print("result:", result)


if __name__ == "__main__":
    asyncio.run(main())

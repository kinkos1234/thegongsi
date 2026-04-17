"""KOSPI/KOSDAQ market 라벨 enrichment (KIND 상장법인목록).

OpenDART corpCode.xml에는 market 구분이 없어 seed 후 UNKNOWN 상태.
KIND(한국예탁결제원) 상장법인목록 HTML을 파싱해 KOSPI/KOSDAQ 매핑 → companies.market 업데이트.

사용:
    python scripts/enrich_market.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

import re

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={mkt}"


_TICKER_TD_RE = re.compile(r"<td[^>]*>\s*(\d{6})\s*</td>")


def _fetch_kind(market_type: str) -> list[str]:
    """KIND 상장법인목록 HTML → 종목코드(6자리) 리스트."""
    url = KIND_URL.format(mkt=market_type)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.content.decode("euc-kr", errors="ignore")
    # <td>NNNNNN</td> 형태 전체 수집 후 dedup
    return list(dict.fromkeys(_TICKER_TD_RE.findall(html)))


def _to_asyncpg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgresql://", 1)
    return url


async def enrich():
    db_url = _to_asyncpg_dsn(os.environ.get("DATABASE_URL", ""))
    if not db_url.startswith("postgres"):
        logger.error("Postgres DB URL 필요"); sys.exit(1)

    logger.info("KIND 상장법인목록 다운로드 중...")
    kospi = _fetch_kind("stockMkt")
    kosdaq = _fetch_kind("kosdaqMkt")
    logger.info(f"KOSPI: {len(kospi)}, KOSDAQ: {len(kosdaq)}")

    if not kospi or not kosdaq:
        logger.error("KIND 파싱 실패 (0건). HTML 구조 변경 가능성."); sys.exit(1)

    import asyncpg
    conn = await asyncpg.connect(db_url)
    try:
        updated_k = await conn.execute(
            "UPDATE companies SET market = 'KOSPI' WHERE ticker = ANY($1::text[])",
            kospi,
        )
        updated_q = await conn.execute(
            "UPDATE companies SET market = 'KOSDAQ' WHERE ticker = ANY($1::text[])",
            kosdaq,
        )
        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM companies WHERE market = 'UNKNOWN'"
        )
        logger.info(f"업데이트: KOSPI {updated_k}, KOSDAQ {updated_q}, UNKNOWN 잔여 {remaining}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(enrich())

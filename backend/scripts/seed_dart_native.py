"""OpenDART corpCode.xml에서 직접 상장사 전체 seed (asyncpg 벌크).

pykrx(KRX 불안정)·dart-fss(hang) 우회. DART API 키 + asyncpg 벌크 INSERT ON CONFLICT.
SQLAlchemy ORM 미사용 — 512MB Fly VM에서 OOM 방지 + 속도 ↑.

사용:
    python scripts/seed_dart_native.py
"""
import asyncio
import io
import logging
import os
import secrets
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts._logging_setup import setup_script_logging
setup_script_logging()
logger = logging.getLogger(__name__)


def _fetch_corp_codes(api_key: str) -> list[dict]:
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    logger.info("OpenDART corpCode.xml 다운로드 중...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.content
    logger.info(f"  → {len(data):,} bytes 수신, 파싱 중")
    corps: list[dict] = []
    # iterparse 스트리밍: ET.parse는 압축 해제된 ~40MB XML을 DOM으로 통째로 들어
    # Fly 512MB VM에서 OOM(SIGKILL)을 일으킨다. element 단위로 처리·clear하고
    # root.clear()로 자식 누적까지 끊어야 메모리가 일정하게 유지된다.
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("CORPCODE.xml") as f:
            context = iter(ET.iterparse(f, events=("start", "end")))
            _, root = next(context)
            for event, elem in context:
                if event != "end" or elem.tag != "list":
                    continue
                def g(tag: str) -> str:
                    el = elem.find(tag)
                    return (el.text or "").strip() if el is not None else ""
                stock_code = g("stock_code")
                if stock_code:
                    corps.append({
                        "corp_code": g("corp_code"),
                        "corp_name": g("corp_name"),
                        "stock_code": stock_code,
                    })
                elem.clear()
                root.clear()
    logger.info("  → XML 파싱 완료")
    return corps


def _to_asyncpg_dsn(url: str) -> str:
    """sqlalchemy URL → asyncpg DSN 변환."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgresql://", 1)
    return url


async def seed():
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY 필요"); sys.exit(1)
    db_url = _to_asyncpg_dsn(os.environ.get("DATABASE_URL", ""))
    if not db_url.startswith("postgres"):
        logger.error(f"Postgres DB URL 필요 (현재: {db_url[:30]})"); sys.exit(1)

    corps = _fetch_corp_codes(api_key)
    logger.info(f"상장사 {len(corps)}개 수신")

    import asyncpg
    conn = await asyncpg.connect(db_url)
    try:
        now = datetime.utcnow()
        rows = [
            (secrets.token_hex(6), c["stock_code"], c["corp_code"], c["corp_name"], "UNKNOWN", now)
            for c in corps
        ]
        # ticker UNIQUE 기준 ON CONFLICT. name_ko/market만 갱신 (market은 UNKNOWN일 때만).
        stmt = """
        INSERT INTO companies (id, ticker, corp_code, name_ko, market, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (ticker) DO UPDATE SET
            corp_code = CASE WHEN companies.corp_code = '' OR companies.corp_code IS NULL
                             THEN EXCLUDED.corp_code ELSE companies.corp_code END,
            name_ko = EXCLUDED.name_ko,
            updated_at = EXCLUDED.updated_at
        """
        batch = 500
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            await conn.executemany(stmt, chunk)
            logger.info(f"  upsert {i + len(chunk)}/{len(rows)}")
    finally:
        await conn.close()
    logger.info("완료")


if __name__ == "__main__":
    asyncio.run(seed())

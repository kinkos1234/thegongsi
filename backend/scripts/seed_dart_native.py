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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _fetch_corp_codes(api_key: str) -> list[dict]:
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    logger.info("OpenDART corpCode.xml 다운로드 중...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.content
    logger.info(f"  → {len(data):,} bytes 수신, 파싱 중")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("CORPCODE.xml") as f:
            tree = ET.parse(f)
    logger.info("  → XML 파싱 완료")
    corps = []
    for item in tree.getroot().findall("list"):
        def g(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""
        stock_code = g("stock_code")
        if not stock_code:
            continue
        corps.append({
            "corp_code": g("corp_code"),
            "corp_name": g("corp_name"),
            "stock_code": stock_code,
        })
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

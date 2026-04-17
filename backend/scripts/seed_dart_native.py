"""OpenDART corpCode.xml에서 직접 상장사 전체 seed.

pykrx(KRX 불안정)·dart-fss(hang) 우회. DART API 키로 corpCode.xml 1회 다운로드.

사용:
    python scripts/seed_dart_native.py
"""
import asyncio
import io
import logging
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.database import init_db, async_session
from app.models.tables import Company

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _fetch_corp_codes(api_key: str) -> list[dict]:
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    logger.info("OpenDART corpCode.xml 다운로드 중...")
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("CORPCODE.xml") as f:
            tree = ET.parse(f)
    root = tree.getroot()
    corps = []
    for item in root.findall("list"):
        def g(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""
        stock_code = g("stock_code")
        if not stock_code:  # 상장사만
            continue
        corps.append({
            "corp_code": g("corp_code"),
            "corp_name": g("corp_name"),
            "stock_code": stock_code,
        })
    return corps


async def seed():
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY 환경변수 필요")
        sys.exit(1)
    await init_db()

    corps = _fetch_corp_codes(api_key)
    logger.info(f"상장사 {len(corps)}개 수신")

    inserted = 0
    updated = 0
    async with async_session() as db:
        for c in corps:
            existing = await db.execute(select(Company).where(Company.ticker == c["stock_code"]))
            row = existing.scalar_one_or_none()
            if row:
                if not row.corp_code:
                    row.corp_code = c["corp_code"]
                if not row.name_ko or row.name_ko != c["corp_name"]:
                    row.name_ko = c["corp_name"]
                updated += 1
            else:
                db.add(Company(
                    ticker=c["stock_code"],
                    corp_code=c["corp_code"],
                    name_ko=c["corp_name"],
                    market=None,  # market은 pykrx 복구 시 별도 보강
                ))
                inserted += 1
        await db.commit()
    logger.info(f"DB: {inserted} inserted, {updated} updated (총 {len(corps)})")


if __name__ == "__main__":
    asyncio.run(seed())

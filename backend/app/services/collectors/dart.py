"""DART 공시 수집기.

dart-fss 라이브러리 사용. 증분 수집(rcept_no 기준) + upsert.
10,000 req/day 한도 — 일일 배치 1회로 충분.

환경 변수: DART_API_KEY
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import Disclosure

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _configure_dart():
    """dart-fss 전역 설정. 모듈 import 시점이 아닌 호출 시점에 초기화."""
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY not configured")
    import dart_fss as dart
    dart.set_api_key(api_key=settings.dart_api_key)
    return dart


def _fetch_filings_sync(bgn_de: str, end_de: str) -> list[dict]:
    """동기 dart-fss 호출. 별도 스레드에서 실행 예정."""
    dart = _configure_dart()
    # 전체 유가증권·코스닥 공시 조회
    search = dart.filings.search(
        bgn_de=bgn_de,
        end_de=end_de,
        last_reprt_at="Y",
        page_count=100,
    )
    rows = []
    for f in search:
        rows.append({
            "rcept_no": f.rcept_no,
            "corp_code": f.corp_code,
            "ticker": (getattr(f, "stock_code", None) or "").strip(),
            "report_nm": f.report_nm,
            "rcept_dt": f.rcept_dt[:4] + "-" + f.rcept_dt[4:6] + "-" + f.rcept_dt[6:8],
            "raw_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={f.rcept_no}",
        })
    return rows


async def fetch_recent_disclosures(days: int = 1) -> dict:
    """최근 N일 공시 수집 → Disclosure upsert.

    증분: 기존 rcept_no는 skip. 이상징후 탐지는 별도 모듈(services/anomaly)이 이후 처리.
    """
    if not settings.dart_api_key:
        logger.warning("DART_API_KEY not set, skipping collection")
        return {"count": 0, "status": "no_api_key"}

    import asyncio

    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days)).strftime("%Y%m%d")

    loop = asyncio.get_event_loop()
    try:
        rows = await loop.run_in_executor(None, _fetch_filings_sync, bgn_de, end_de)
    except Exception as e:
        logger.exception("DART fetch failed")
        return {"count": 0, "error": str(e)}

    inserted = 0
    skipped = 0
    async with async_session() as db:
        for row in rows:
            existing = await db.execute(select(Disclosure).where(Disclosure.rcept_no == row["rcept_no"]))
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            if not row["ticker"]:
                # 상장법인만 (6자리 종목코드가 있는 경우)
                skipped += 1
                continue
            db.add(Disclosure(**row))
            inserted += 1
        await db.commit()

    logger.info(f"DART: {inserted} inserted, {skipped} skipped (period {bgn_de}~{end_de})")
    return {"count": inserted, "skipped": skipped, "bgn_de": bgn_de, "end_de": end_de}

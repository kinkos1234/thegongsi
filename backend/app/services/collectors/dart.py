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


def _fetch_by_corp_sync(corp_code: str, bgn_de: str, end_de: str) -> list[dict]:
    """특정 corp_code의 공시만 조회."""
    dart = _configure_dart()
    search = dart.filings.search(
        corp_code=corp_code,
        bgn_de=bgn_de,
        end_de=end_de,
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


async def backfill_ticker(ticker: str, days: int = 90) -> dict:
    """watchlist 신규 추가 종목 백필.

    Company.corp_code 필요. 없으면 dart-fss corp_list로 찾아서 Company.upsert.
    """
    if not settings.dart_api_key:
        return {"status": "no_api_key"}

    import asyncio
    from sqlalchemy import select
    from app.database import async_session
    from app.models.tables import Company, Disclosure

    # corp_code 조회
    async with async_session() as db:
        res = await db.execute(select(Company).where(Company.ticker == ticker))
        company = res.scalar_one_or_none()

    loop = asyncio.get_event_loop()

    if not company or not company.corp_code:
        # dart corp_list에서 검색
        def _find_corp():
            dart = _configure_dart()
            corp_list = dart.get_corp_list()
            matches = [c for c in corp_list if getattr(c, "stock_code", None) == ticker]
            return matches[0] if matches else None

        corp = await loop.run_in_executor(None, _find_corp)
        if not corp:
            return {"status": "not_listed", "ticker": ticker}

        async with async_session() as db:
            if company:
                company.corp_code = corp.corp_code
                company.name_ko = corp.corp_name
            else:
                db.add(Company(
                    ticker=ticker,
                    corp_code=corp.corp_code,
                    name_ko=corp.corp_name,
                    market="KOSPI",  # 정확한 시장 구분은 추가 API 필요, Phase 2
                ))
            await db.commit()
        corp_code = corp.corp_code
    else:
        corp_code = company.corp_code

    # 기간 계산
    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days)).strftime("%Y%m%d")

    try:
        rows = await loop.run_in_executor(None, _fetch_by_corp_sync, corp_code, bgn_de, end_de)
    except Exception as e:
        logger.exception(f"backfill {ticker} failed")
        return {"status": "error", "error": str(e)}

    inserted = 0
    async with async_session() as db:
        for row in rows:
            if not row["ticker"]:
                row["ticker"] = ticker  # corp_code 기반 검색이라 stock_code 비어있을 수 있음
            existing = await db.execute(select(Disclosure).where(Disclosure.rcept_no == row["rcept_no"]))
            if existing.scalar_one_or_none():
                continue
            db.add(Disclosure(**row))
            inserted += 1
        await db.commit()

    logger.info(f"Backfill {ticker} ({corp_code}): {inserted} new, {len(rows)} total in {days}d")

    # anomaly scan 연쇄
    from app.services.anomaly.detector import scan_new_disclosures
    anomaly = await scan_new_disclosures()

    return {
        "status": "ok",
        "ticker": ticker,
        "corp_code": corp_code,
        "days": days,
        "fetched": len(rows),
        "inserted": inserted,
        "anomaly": anomaly,
    }


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

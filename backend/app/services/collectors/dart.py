"""DART 공시 수집기.

dart-fss 라이브러리 사용. 증분 수집(rcept_no 기준) + upsert.
10,000 req/day 한도 — 일일 배치 1회 + on-demand backfill.

Rate-limit 전략:
- corp_list(CORPCODE.zip)는 프로세스 생존 동안 1회만 로드 (`_corp_list_cache`)
- 동시 backfill은 `_backfill_sem` 세마포어(max 3)로 제한 → 외부 호출 폭주 방지

환경 변수: DART_API_KEY
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import Disclosure

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 동시 backfill 제한 (DART 서버 보호)
_backfill_sem = asyncio.Semaphore(3)

# corp_list 메모리 캐시 — CORPCODE.zip은 3MB, 재다운로드 비용 큼
_corp_list_cache = None


def _get_corp_list():
    global _corp_list_cache
    if _corp_list_cache is None:
        dart = _configure_dart()
        _corp_list_cache = dart.get_corp_list()
    return _corp_list_cache


def _configure_dart():
    """dart-fss 전역 설정. 모듈 import 시점이 아닌 호출 시점에 초기화."""
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY not configured")
    import dart_fss as dart
    dart.set_api_key(api_key=settings.dart_api_key)
    return dart


def _fetch_filings_sync(bgn_de: str, end_de: str, max_rows: int = 2000) -> list[dict]:
    """전체 시장 일일 수집. 페이지네이션 버그 수정 (routine 필터는 daily에도 적용)."""
    dart = _configure_dart()
    rows: list[dict] = []
    page_no = 1
    while len(rows) < max_rows:
        search = dart.filings.search(
            bgn_de=bgn_de,
            end_de=end_de,
            last_reprt_at="Y",
            page_count=100,
            page_no=page_no,
        )
        page_items = list(search)
        if not page_items:
            break
        for f in page_items:
            if any(p in f.report_nm for p in ROUTINE_PATTERNS):
                continue
            rows.append({
                "rcept_no": f.rcept_no,
                "corp_code": f.corp_code,
                "ticker": (getattr(f, "stock_code", None) or "").strip(),
                "report_nm": f.report_nm,
                "rcept_dt": f.rcept_dt[:4] + "-" + f.rcept_dt[4:6] + "-" + f.rcept_dt[6:8],
                "raw_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={f.rcept_no}",
            })
            if len(rows) >= max_rows:
                break
        total_page = getattr(search, "total_page", page_no)
        if page_no >= total_page:
            break
        page_no += 1
    return rows


# 대형주 노이즈 필터 — 이 패턴의 공시는 backfill에서 제외 (DD 메모·anomaly에 무가치)
ROUTINE_PATTERNS = (
    "임원ㆍ주요주주특정증권등소유상황보고서",
    "최대주주등소유주식변동신고서",
    "주식등의대량보유상황보고서",
)

MAX_BACKFILL_ROWS = 500  # 대형주 폭탄 대비 상한


def _fetch_by_corp_sync(corp_code: str, bgn_de: str, end_de: str, max_rows: int = MAX_BACKFILL_ROWS) -> list[dict]:
    """특정 corp_code 공시 전체 페이지네이션.

    - 모든 페이지 순회 (이전에는 iteration이 1페이지에서 멈춤 — dart-fss 0.4.15 이슈)
    - ROUTINE_PATTERNS에 해당하는 routine 공시는 제외 (노이즈)
    - max_rows 도달 시 조기 종료 (대형주는 365일 2000+건)
    """
    dart = _configure_dart()
    rows: list[dict] = []
    page_no = 1
    while len(rows) < max_rows:
        search = dart.filings.search(
            corp_code=corp_code,
            bgn_de=bgn_de,
            end_de=end_de,
            page_count=100,
            page_no=page_no,
        )
        page_items = list(search)
        if not page_items:
            break
        for f in page_items:
            # routine 공시 필터
            if any(p in f.report_nm for p in ROUTINE_PATTERNS):
                continue
            rows.append({
                "rcept_no": f.rcept_no,
                "corp_code": f.corp_code,
                "ticker": (getattr(f, "stock_code", None) or "").strip(),
                "report_nm": f.report_nm,
                "rcept_dt": f.rcept_dt[:4] + "-" + f.rcept_dt[4:6] + "-" + f.rcept_dt[6:8],
                "raw_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={f.rcept_no}",
            })
            if len(rows) >= max_rows:
                break
        total_page = getattr(search, "total_page", page_no)
        if page_no >= total_page:
            break
        page_no += 1
    return rows


async def backfill_ticker(ticker: str, days: int = 90) -> dict:
    """watchlist 신규 추가 종목 백필.

    Company.corp_code 필요. 없으면 dart-fss corp_list(캐시)로 찾아서 Company.upsert.
    동시 실행은 세마포어로 max 3으로 제한.
    """
    async with _backfill_sem:
        return await _backfill_ticker_impl(ticker, days)


async def _backfill_ticker_impl(ticker: str, days: int) -> dict:
    if not settings.dart_api_key:
        return {"status": "no_api_key"}

    from sqlalchemy import select
    from app.database import async_session
    from app.models.tables import Company, Disclosure

    # corp_code 조회
    async with async_session() as db:
        res = await db.execute(select(Company).where(Company.ticker == ticker))
        company = res.scalar_one_or_none()

    loop = asyncio.get_event_loop()

    if not company or not company.corp_code:
        # dart corp_list에서 검색 (캐시 사용)
        def _find_corp():
            corp_list = _get_corp_list()
            matches = [c for c in corp_list if getattr(c, "stock_code", None) == ticker]
            return matches[0] if matches else None

        corp = await loop.run_in_executor(None, _find_corp)
        if not corp:
            return {"status": "not_listed", "ticker": ticker}

        # corp_cls: 'Y'=KOSPI, 'K'=KOSDAQ. market_type: stockMkt/kosdaqMkt
        market = "KOSPI" if getattr(corp, "corp_cls", "Y") == "Y" else "KOSDAQ"
        sector = getattr(corp, "sector", None)
        async with async_session() as db:
            if company:
                company.corp_code = corp.corp_code
                company.name_ko = corp.corp_name
                company.market = market
                if sector and not company.sector:
                    company.sector = sector
            else:
                db.add(Company(
                    ticker=ticker,
                    corp_code=corp.corp_code,
                    name_ko=corp.corp_name,
                    market=market,
                    sector=sector,
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

    # Neo4j 그래프 동기화 (ticker 한정)
    graph_result = {"status": "skipped"}
    try:
        from app.services.graph.sync import sync_disclosures
        graph_result = await sync_disclosures(tickers=[ticker])
    except Exception as e:
        logger.warning(f"graph sync for {ticker} failed: {e}")
        graph_result = {"status": "error", "error": str(e)}

    return {
        "status": "ok",
        "ticker": ticker,
        "corp_code": corp_code,
        "days": days,
        "fetched": len(rows),
        "inserted": inserted,
        "anomaly": anomaly,
        "graph": graph_result,
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

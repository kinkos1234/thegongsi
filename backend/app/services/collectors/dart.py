"""DART 공시 수집기 — 직접 OpenDART REST 호출 (v2, dart-fss 제거).

이전: dart-fss 라이브러리가 매 호출마다 key 검증 round-trip을 DART로 발생시켜
      throttle 상황에서 backfill 전체 블록.
v2: requests 직접 호출 — 불필요한 검증 제거, 실패 시에도 체인 다른 단계(메모·이벤트)는 유지.

10,000 req/day 한도 — 일일 배치 1회 + on-demand backfill.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import Disclosure

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 동시 backfill 제한 (DART 서버 보호)
_backfill_sem = asyncio.Semaphore(3)

# 대형주 노이즈 필터
ROUTINE_PATTERNS = (
    "임원ㆍ주요주주특정증권등소유상황보고서",
    "최대주주등소유주식변동신고서",
    "주식등의대량보유상황보고서",
)

MAX_BACKFILL_ROWS = 500

DART_BASE = "https://opendart.fss.or.kr/api"


# ---------- 레거시 호환: corpCode.xml 기반 corp_list ----------
# seed_market_index.py의 `_fetch_from_dart_corp_list` fallback이 이 함수를 참조.
# dart-fss를 걷어낸 대신 경량 네임드튜플 + 직접 download로 제공.
_corp_list_cache: list | None = None


class _DartCorp:  # 기존 dart_fss.corp 객체 shape 일부 흉내
    __slots__ = ("corp_code", "corp_name", "stock_code", "corp_cls")

    def __init__(self, corp_code: str, corp_name: str, stock_code: str, corp_cls: str):
        self.corp_code = corp_code
        self.corp_name = corp_name
        self.stock_code = stock_code or None
        self.corp_cls = corp_cls  # 'Y' / 'K' / 기타 — OpenDART raw에는 없어 N으로 기본값


def _get_corp_list():
    """OpenDART corpCode.xml → _DartCorp 리스트. 프로세스 수명 동안 1회 캐시.

    raw XML에는 corp_cls가 없으므로 'N' 기본값. 상장시장 구분이 필요한 사용처(예: KOSPI/KOSDAQ 필터)는
    KIND(enrich_market.py) 결과를 DB에서 조회하도록 설계 권장.
    """
    global _corp_list_cache
    if _corp_list_cache is not None:
        return _corp_list_cache
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY not configured")

    import io
    import xml.etree.ElementTree as ET
    import zipfile

    url = f"{DART_BASE}/corpCode.xml"
    resp = requests.get(url, params={"crtfc_key": settings.dart_api_key}, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("CORPCODE.xml") as f:
            tree = ET.parse(f)
    corps: list[_DartCorp] = []
    for item in tree.getroot().findall("list"):
        def g(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""
        corps.append(
            _DartCorp(
                corp_code=g("corp_code"),
                corp_name=g("corp_name"),
                stock_code=g("stock_code"),
                corp_cls="N",
            )
        )
    _corp_list_cache = corps
    logger.info(f"corpCode.xml 캐시 로드: {len(corps)}개 (상장사 {sum(1 for c in corps if c.stock_code)}개)")
    return corps


def _normalize_date(raw: str) -> str:
    """YYYYMMDD → YYYY-MM-DD."""
    s = (raw or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _row_from_filing(item: dict) -> dict:
    return {
        "rcept_no": item.get("rcept_no", ""),
        "corp_code": item.get("corp_code", ""),
        "ticker": (item.get("stock_code") or "").strip(),
        "report_nm": item.get("report_nm", "").strip(),
        "rcept_dt": _normalize_date(item.get("rcept_dt", "")),
        "raw_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no', '')}",
    }


def _fetch_list(
    *,
    corp_code: str | None = None,
    bgn_de: str,
    end_de: str,
    max_rows: int,
    pblntf_ty: str | None = None,
    last_reprt_at: str | None = None,
) -> list[dict]:
    """OpenDART /api/list.json 페이지네이션 + routine 필터 + max_rows cutoff."""
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY not configured")

    rows: list[dict] = []
    page_no = 1
    while len(rows) < max_rows:
        params: dict[str, Any] = {
            "crtfc_key": settings.dart_api_key,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": 100,
            "page_no": page_no,
        }
        if corp_code:
            params["corp_code"] = corp_code
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty
        if last_reprt_at:
            params["last_reprt_at"] = last_reprt_at

        try:
            resp = requests.get(f"{DART_BASE}/list.json", params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"DART list.json page {page_no} 실패: {e}")
            break

        status = data.get("status")
        if status not in ("000", "013"):
            logger.warning(f"DART list.json status={status} msg={data.get('message')}")
            break
        if status == "013":
            break  # no data

        items = data.get("list") or []
        if not items:
            break

        for item in items:
            if any(p in item.get("report_nm", "") for p in ROUTINE_PATTERNS):
                continue
            rows.append(_row_from_filing(item))
            if len(rows) >= max_rows:
                break

        total_page = data.get("total_page", page_no)
        if page_no >= total_page:
            break
        page_no += 1
    return rows


async def backfill_ticker(ticker: str, days: int = 90) -> dict:
    """watchlist 신규 추가 종목 백필 — 세마포어 max 3."""
    async with _backfill_sem:
        return await _backfill_ticker_impl(ticker, days)


async def _backfill_ticker_impl(ticker: str, days: int) -> dict:
    if not settings.dart_api_key:
        return {"status": "no_api_key"}

    from app.models.tables import Company

    async with async_session() as db:
        res = await db.execute(select(Company).where(Company.ticker == ticker))
        company = res.scalar_one_or_none()

    if not company or not company.corp_code:
        # 시드가 없으면 스킵 — seed_dart_native.py를 먼저 실행해야 함.
        return {"status": "not_listed", "ticker": ticker}

    corp_code = company.corp_code

    # 기간 계산
    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days)).strftime("%Y%m%d")

    loop = asyncio.get_event_loop()
    try:
        rows = await loop.run_in_executor(
            None,
            lambda: _fetch_list(
                corp_code=corp_code, bgn_de=bgn_de, end_de=end_de, max_rows=MAX_BACKFILL_ROWS
            ),
        )
    except Exception as e:
        logger.exception(f"backfill {ticker} failed")
        return {"status": "error", "error": str(e), "corp_code": corp_code}

    inserted = 0
    async with async_session() as db:
        for row in rows:
            if not row["ticker"]:
                row["ticker"] = ticker
            existing = await db.execute(
                select(Disclosure).where(Disclosure.rcept_no == row["rcept_no"])
            )
            if existing.scalar_one_or_none():
                continue
            db.add(Disclosure(**row))
            inserted += 1
        await db.commit()

    logger.info(f"Backfill {ticker} ({corp_code}): {inserted} new, {len(rows)} total in {days}d")

    # anomaly scan 연쇄
    from app.services.anomaly.detector import scan_new_disclosures
    try:
        anomaly = await scan_new_disclosures()
    except Exception as e:
        logger.warning(f"anomaly scan for {ticker} failed: {e}")
        anomaly = {"status": "error", "error": str(e)}

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


async def fetch_recent_disclosures(days: int = 3) -> dict:
    """최근 N일 전시장 공시 수집 → Disclosure upsert (daily cron용).

    기본 3일 슬라이딩 윈도우 — 주말/공휴일 + Actions 지연 대비해 소폭 겹치게 수집.
    rcept_no UNIQUE 제약으로 중복은 skip되어 idempotent.
    """
    if not settings.dart_api_key:
        logger.warning("DART_API_KEY not set, skipping collection")
        return {"count": 0, "status": "no_api_key"}

    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days)).strftime("%Y%m%d")

    loop = asyncio.get_event_loop()
    try:
        rows = await loop.run_in_executor(
            None,
            lambda: _fetch_list(
                bgn_de=bgn_de, end_de=end_de, max_rows=2000, last_reprt_at="Y"
            ),
        )
    except Exception as e:
        logger.exception("DART fetch failed")
        return {"count": 0, "error": str(e)}

    inserted = 0
    skipped = 0
    async with async_session() as db:
        for row in rows:
            existing = await db.execute(
                select(Disclosure).where(Disclosure.rcept_no == row["rcept_no"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            if not row["ticker"]:
                skipped += 1
                continue
            db.add(Disclosure(**row))
            inserted += 1
        await db.commit()

    logger.info(f"DART: {inserted} inserted, {skipped} skipped (period {bgn_de}~{end_de})")
    return {"count": inserted, "skipped": skipped, "bgn_de": bgn_de, "end_de": end_de}

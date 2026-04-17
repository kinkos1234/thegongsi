"""권리락/배당락 등 ex-date 이벤트 수집기.

OpenDART 주요사항보고서 중:
  - 유상증자결정 (/api/piicDecsn.json)          → 구주주청약일, 권리락일 관련
  - 무상증자결정 (/api/fricDecsn.json)
  - 주식배당결정 (/api/stkDvdendDecsn.json)    → 기준일 + 배당락
  - 현금·현물배당결정 (/api/cashDvdendDecsn.json) → 기준일 + 지급예정일

각 엔드포인트는 공시된 문서의 주요 필드를 JSON으로 반환.
이를 CalendarEvent 테이블에 upsert하여 D-7 캘린더 위젯 소스로 사용.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

DART_ENDPOINTS = {
    "piicDecsn": {
        "label": "유상증자결정",
        # bfcorp_rgt_de(권리부최종매매일), afcrp_rgt_de(권리락일)
        "events": [
            ("afcrp_rgt_de", "ex_right"),
            ("bfcorp_rgt_de", "last_with_right"),
        ],
    },
    "fricDecsn": {
        "label": "무상증자결정",
        "events": [
            ("nstk_ascrtn_de", "record_date"),
            ("nstk_isstk_lstg_pd_de", "listing_date"),
        ],
    },
    "pifricDecsn": {
        "label": "유무상증자결정",
        "events": [
            ("afcrp_rgt_de", "ex_right"),
            ("bfcorp_rgt_de", "last_with_right"),
            ("nstk_ascrtn_de", "record_date"),
        ],
    },
    # NOTE: 현금·현물배당 ex-date는 OpenDART 주요사항보고서 구조화 API로 제공되지 않음.
    # 정기보고서 alotMatter(배당 요약)만 가능. 배당 ex-date는 다음 Phase에서 KRX 기업공시 스크래핑 또는
    # 사업보고서 본문 파싱으로 확장 예정.
}


def _normalize_date(raw: str | None) -> str | None:
    """DART 날짜 필드는 'YYYY-MM-DD' or 'YYYYMMDD' or '-' or 공백 → 'YYYY-MM-DD' or None."""
    if not raw:
        return None
    s = str(raw).strip().replace("/", "-")
    if not s or s in ("-", "미정", ""):
        return None
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    return None


def _dart_fetch(endpoint: str, corp_code: str, bgn_de: str, end_de: str, api_key: str) -> list[dict]:
    url = f"https://opendart.fss.or.kr/api/{endpoint}.json"
    params = {"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": bgn_de, "end_de": end_de}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"DART {endpoint} {corp_code} 실패: {e}")
        return []
    if data.get("status") not in ("000", "013"):
        # 013 = 조회된 데이터 없음 (정상)
        if data.get("status") != "013":
            logger.debug(f"DART {endpoint} status={data.get('status')} msg={data.get('message')}")
        return []
    return data.get("list", []) or []


def _rows_from_filing(corp_code: str, ticker: str, endpoint: str, filing: dict) -> Iterable[dict]:
    """하나의 주요사항보고서 filing → 복수 CalendarEvent dict."""
    spec = DART_ENDPOINTS[endpoint]
    rcept_no = filing.get("rcept_no", "")
    title = f"{spec['label']} ({filing.get('report_nm', '').strip() or endpoint})"
    for date_field, event_type in spec["events"]:
        event_date = _normalize_date(filing.get(date_field))
        if not event_date:
            continue
        yield {
            "id": secrets.token_hex(6),
            "ticker": ticker,
            "event_type": event_type,
            "event_date": event_date,
            "rcept_no": rcept_no,
            "title": title,
            "notes": None,
            "fetched_at": datetime.now(KST).replace(tzinfo=None),
        }


async def scan_ex_dates(
    tickers: list[tuple[str, str]],  # [(ticker, corp_code), ...]
    days_back: int = 60,
    api_key: str | None = None,
) -> list[dict]:
    """지정 종목군의 최근 days_back일 내 공시에서 ex-date 이벤트 추출."""
    api_key = api_key or os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY 미설정")
        return []
    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days_back)).strftime("%Y%m%d")

    all_events: list[dict] = []
    for ticker, corp_code in tickers:
        if not corp_code:
            continue
        for endpoint in DART_ENDPOINTS:
            filings = _dart_fetch(endpoint, corp_code, bgn_de, end_de, api_key)
            for f in filings:
                all_events.extend(_rows_from_filing(corp_code, ticker, endpoint, f))
    logger.info(f"scan_ex_dates: {len(tickers)} tickers × 4 endpoints → {len(all_events)} events")
    return all_events


async def upsert_events(conn, events: list[dict]) -> int:
    """asyncpg connection으로 calendar_events 벌크 upsert."""
    if not events:
        return 0
    rows = [
        (e["id"], e["ticker"], e["event_type"], e["event_date"],
         e["rcept_no"], e["title"], e["notes"], e["fetched_at"])
        for e in events
    ]
    stmt = """
    INSERT INTO calendar_events
        (id, ticker, event_type, event_date, rcept_no, title, notes, fetched_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (ticker, event_type, event_date, rcept_no)
    DO UPDATE SET title = EXCLUDED.title, fetched_at = EXCLUDED.fetched_at
    """
    await conn.executemany(stmt, rows)
    return len(rows)

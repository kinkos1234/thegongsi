"""list.json 기반 ex-date 스캐너 (유/무상증자 권리락일).

이전 `ex_dates.py`는 종목별 piicDecsn 호출 → 2,616 × 3 = 7,848 API calls.
v2는 전 시장 list.json 1회로 필터링 → 필요 rcept_no만 document.xml 파싱.
일일 증분 시 ~5-10 calls로 충분.

전략:
  1. /api/list.json?pblntf_ty=B&bgn_de=...&end_de=... (주요사항보고서 전체)
  2. report_nm 필터: '유상증자결정', '무상증자결정', '유무상증자결정'
  3. 각 filing의 rcept_no로 document.xml(ZIP) 본문 파싱 (배당과 동일 패턴)
  4. "N. 신주배정기준일"·"N. 권리락예정일"·"N. 권리락기준일" 등 date field 추출
  5. calendar_events upsert
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import secrets
import zipfile
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# list.json 필터 대상 제목 (prefix match 권장)
TARGET_TITLE_PATTERNS = [
    "유상증자결정",
    "무상증자결정",
    "유·무상증자결정",
    "유무상증자결정",
]

# document.xml HTML 표에서 <td>N. 라벨</td> … <span class="xforms_input">값</span> 추출
FIELD_RE = re.compile(
    r'<td[^>]*>\s*<span[^>]*>\s*(\d+)\.\s*([^<]+?)\s*</span>.*?'
    r'<span[^>]*class="xforms_input"[^>]*>\s*([^<]*?)\s*</span>',
    re.DOTALL,
)
DATE_RE = re.compile(r"(\d{4})[-./\s년]+(\d{1,2})[-./\s월]+(\d{1,2})")

# 라벨(한글) → 이벤트 타입 매핑 — 실제 유/무상증자 공시 표준 라벨 기반
LABEL_TO_EVENT = [
    ("권리락", "ex_right"),
    ("신주배정기준일", "record_date"),
    ("납입일", "payment_date"),
    ("신주의상장예정일", "listing_date"),
    ("상장예정일", "listing_date"),
    ("청약일", "subscription_date"),
]


def _parse_date(raw: str) -> str | None:
    m = DATE_RE.search(raw or "")
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


async def _fetch_list(
    client: httpx.AsyncClient,
    bgn_de: str,
    end_de: str,
    api_key: str,
) -> list[dict]:
    """list.json 페이지네이션 수집. pblntf_ty=B(주요사항보고서)."""
    all_items: list[dict] = []
    page_no = 1
    while True:
        params = {
            "crtfc_key": api_key,
            "pblntf_ty": "B",
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": page_no,
            "page_count": 100,
        }
        try:
            r = await client.get("https://opendart.fss.or.kr/api/list.json", params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning(f"list.json page {page_no} 실패: {e}")
            break
        if data.get("status") not in ("000", "013"):
            logger.warning(f"list.json status={data.get('status')} msg={data.get('message')}")
            break
        items = data.get("list") or []
        all_items.extend(items)
        total_page = data.get("total_page", 1)
        if page_no >= total_page or not items:
            break
        page_no += 1
    return all_items


async def _fetch_document(client: httpx.AsyncClient, rcept_no: str, api_key: str) -> str | None:
    url = "https://opendart.fss.or.kr/api/document.xml"
    for attempt in range(3):
        try:
            r = await client.get(url, params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=20)
            r.raise_for_status()
            data = r.content
            if not data.startswith(b"PK"):
                return None
            zf = zipfile.ZipFile(io.BytesIO(data))
            names = zf.namelist()
            if not names:
                return None
            raw = zf.open(names[0]).read()
            for enc in ("utf-8", "euc-kr", "cp949"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == 2:
                logger.warning(f"document.xml {rcept_no} 실패: {type(e).__name__} {e}")
                return None
            await asyncio.sleep(0.5 * (attempt + 1))


def _extract_fields(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in FIELD_RE.finditer(html):
        fields[m.group(2).strip()] = m.group(3).strip()
    return fields


def _events_from_fields(ticker: str, rcept_no: str, report_nm: str, fields: dict[str, str]) -> Iterable[dict]:
    now = datetime.now(KST).replace(tzinfo=None)
    base = {
        "ticker": ticker,
        "rcept_no": rcept_no,
        "title": report_nm.strip(),
        "notes": None,
        "fetched_at": now,
    }
    seen: set[tuple[str, str]] = set()
    for label, val in fields.items():
        # 라벨 정규화 (공백·괄호 제거)
        norm = re.sub(r"[\s\(\)]+", "", label)
        for kw, ev_type in LABEL_TO_EVENT:
            if kw in norm:
                d = _parse_date(val)
                if not d:
                    break
                key = (ev_type, d)
                if key in seen:
                    break
                seen.add(key)
                yield {**base, "id": secrets.token_hex(6), "event_type": ev_type, "event_date": d}
                break


def _matches_target(report_nm: str) -> bool:
    nm = report_nm or ""
    return any(pat in nm for pat in TARGET_TITLE_PATTERNS)


async def scan_ex_dates_v2(
    days_back: int = 180,
    api_key: str | None = None,
    concurrency: int = 5,
) -> list[dict]:
    """주어진 기간 내 유/무상증자 권리락 이벤트 전량 수집."""
    api_key = api_key or os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY 미설정")
        return []

    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days_back)).strftime("%Y%m%d")

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        filings = await _fetch_list(client, bgn_de, end_de, api_key)
        logger.info(f"list.json: {len(filings)}건 수신")
        targets = [f for f in filings if _matches_target(f.get("report_nm", ""))]
        logger.info(f"유/무상증자 필터: {len(targets)}건")
        if not targets:
            return []

        sem = asyncio.Semaphore(concurrency)

        async def _one(f: dict):
            rcept_no = f.get("rcept_no", "")
            ticker = f.get("stock_code", "") or ""
            if not ticker or not rcept_no:
                return []
            async with sem:
                html = await _fetch_document(client, rcept_no, api_key)
            if not html:
                return []
            fields = _extract_fields(html)
            return list(_events_from_fields(ticker, rcept_no, f.get("report_nm", ""), fields))

        results = await asyncio.gather(*[_one(f) for f in targets])
    events = [e for sub in results for e in sub]
    logger.info(f"scan_ex_dates_v2: {len(targets)}건 filings → {len(events)} events")
    return events

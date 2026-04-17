"""배당(현금·현물·주식) ex-date 추출기 — OpenDART document.xml 본문 파싱.

OpenDART 주요사항보고서 구조화 API에 배당 전용이 없음.
거래소 공시('현금·현물배당결정', '주식배당결정')의 `rcept_no`로 document.xml(ZIP)을 받아
HTML 표 구조("N. 배당기준일" → xforms_input 값)에서 날짜 필드를 정규식으로 추출.

배당락일(ex_dividend) = 배당기준일 T-1 영업일 (월~금 단순 계산, 휴장일 미반영).
근사치로 충분 — 홈 위젯은 기준일 자체를 보여주는 게 더 안전.
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

# <td>...<span>N. 라벨</span>...<span class="xforms_input">값</span>
FIELD_RE = re.compile(
    r'<td[^>]*>\s*<span[^>]*>\s*(\d+)\.\s*([^<]+?)\s*</span>.*?'
    r'<span[^>]*class="xforms_input"[^>]*>\s*([^<]*?)\s*</span>',
    re.DOTALL,
)

DATE_RE = re.compile(r"(\d{4})[-./\s년]+(\d{1,2})[-./\s월]+(\d{1,2})")


def _parse_date(raw: str) -> str | None:
    m = DATE_RE.search(raw or "")
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


_KR_HOLIDAYS_CACHE: set[str] | None = None


def _kr_holidays() -> set[str]:
    """holidays 패키지 있으면 KR 공휴일 set, 없으면 빈 set."""
    global _KR_HOLIDAYS_CACHE
    if _KR_HOLIDAYS_CACHE is not None:
        return _KR_HOLIDAYS_CACHE
    try:
        import holidays  # type: ignore
        h = holidays.country_holidays("KR", years=[2023, 2024, 2025, 2026, 2027])
        _KR_HOLIDAYS_CACHE = {d.isoformat() for d in h.keys()}
    except Exception:
        _KR_HOLIDAYS_CACHE = set()
    return _KR_HOLIDAYS_CACHE


def _prev_business_day(iso: str) -> str | None:
    """배당기준일 T-1 거래일. KR 공휴일 회피 (holidays 패키지 있을 때).

    한국 증시는 연말 12/31 휴장도 적용 → 캐시에 포함.
    """
    try:
        d = date.fromisoformat(iso) - timedelta(days=1)
        hs = _kr_holidays()
        # 연말 12/31 휴장도 추가
        extra_holidays = {f"{y}-12-31" for y in range(2023, 2028)}
        while d.weekday() >= 5 or d.isoformat() in hs or d.isoformat() in extra_holidays:
            d -= timedelta(days=1)
        return d.isoformat()
    except Exception:
        return None


async def _fetch_document(client: httpx.AsyncClient, rcept_no: str, api_key: str) -> str | None:
    url = "https://opendart.fss.or.kr/api/document.xml"
    for attempt in range(3):
        try:
            r = await client.get(url, params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=20)
            r.raise_for_status()
            data = r.content
            if not data.startswith(b"PK"):
                # JSON error body
                logger.debug(f"document.xml non-zip for {rcept_no}: {data[:120]}")
                return None
            zf = zipfile.ZipFile(io.BytesIO(data))
            names = zf.namelist()
            if not names:
                return None
            raw = zf.open(names[0]).read()
            # DART XML 기본 UTF-8, 일부 구 문서 EUC-KR
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
        label = m.group(2).strip()
        val = m.group(3).strip()
        fields[label] = val
    return fields


def _build_events(ticker: str, rcept_no: str, report_nm: str, fields: dict[str, str]) -> Iterable[dict]:
    now = datetime.now(KST).replace(tzinfo=None)
    base = {
        "id": secrets.token_hex(6),
        "ticker": ticker,
        "rcept_no": rcept_no,
        "title": report_nm.strip() or "배당결정",
        "notes": None,
        "fetched_at": now,
    }

    # 배당기준일 → record_date + ex_dividend (기준일 T-1BD)
    for label, val in fields.items():
        if "배당기준일" in label or "기준일" == label.strip():
            d = _parse_date(val)
            if d:
                yield {**base, "id": secrets.token_hex(6), "event_type": "record_date", "event_date": d}
                ex = _prev_business_day(d)
                if ex:
                    yield {**base, "id": secrets.token_hex(6), "event_type": "ex_dividend", "event_date": ex}
        elif "지급" in label and ("예정" in label or "일자" in label):
            d = _parse_date(val)
            if d:
                yield {**base, "id": secrets.token_hex(6), "event_type": "payment_date", "event_date": d}


async def scan_dividends_by_rcept(
    filings: list[tuple[str, str, str]],  # [(ticker, rcept_no, report_nm), ...]
    concurrency: int = 3,
    api_key: str | None = None,
) -> list[dict]:
    api_key = api_key or os.environ.get("DART_API_KEY", "")
    if not api_key:
        logger.error("DART_API_KEY 미설정")
        return []

    sem = asyncio.Semaphore(concurrency)

    async def _one(client: httpx.AsyncClient, ticker: str, rcept_no: str, report_nm: str):
        async with sem:
            html = await _fetch_document(client, rcept_no, api_key)
        if not html:
            return []
        fields = _extract_fields(html)
        if not fields:
            return []
        return list(_build_events(ticker, rcept_no, report_nm, fields))

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        results = await asyncio.gather(*[_one(client, t, r, n) for t, r, n in filings])
    return [e for sub in results for e in sub]

"""실적 공정공시(잠정실적·확정실적) 수집기.

OpenDART list.json pblntf_ty=I (공정공시)에서 "잠정실적" / "영업(잠정)실적" 포함 filings만 필터.
본문 document.xml에서 매출액·영업이익·당기순이익 숫자 파싱 (best-effort, 실패 시 null).
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import secrets
import zipfile
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

DART_BASE = "https://opendart.fss.or.kr/api"

EARNINGS_TITLE_PATTERNS = (
    "영업(잠정)실적",
    "영업 잠정실적",
    "영업 (잠정) 실적",
    "잠정실적",
    "확정실적",
)

# "202X년 1분기" / "2025년 3Q" / "2025년 반기" / "2025년 연결"
QUARTER_RE = re.compile(r"(\d{4})\s*년\s*(1|2|3|4|\d)\s*분기|(\d{4})\s*년\s*(1|2|3|4)Q|(\d{4})\s*년\s*반기|(\d{4})\s*년\s*연간")

# 본문 표에서 "N. 매출액" → xforms_input 값
FIELD_RE = re.compile(
    r'<td[^>]*>\s*<span[^>]*>\s*(\d+)\.\s*([^<]+?)\s*</span>.*?'
    r'<span[^>]*class="xforms_input"[^>]*>\s*([^<]*?)\s*</span>',
    re.DOTALL,
)


def _parse_num(raw: str | None) -> float | None:
    if not raw:
        return None
    s = str(raw).strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "—"):
        return None
    # 마이너스 괄호 처리 (-1,234) or (1,234)
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    if s.startswith("-"):
        neg = True
        s = s[1:]
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def _derive_quarter(report_nm: str) -> str:
    m = QUARTER_RE.search(report_nm or "")
    if m:
        grp = m.groups()
        year = next((g for g in grp if g and len(g) == 4), "")
        qnum = next((g for g in grp if g and len(g) == 1), "")
        if "반기" in (report_nm or ""):
            return f"{year}-H1"
        if "연간" in (report_nm or ""):
            return f"{year}-FY"
        if year and qnum:
            return f"{year}-Q{qnum}"
    return ""


def _fetch_list(bgn_de: str, end_de: str, api_key: str, max_rows: int = 1000) -> list[dict]:
    rows: list[dict] = []
    page_no = 1
    while len(rows) < max_rows:
        params = {
            "crtfc_key": api_key,
            "pblntf_ty": "I",  # 공정공시
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": 100,
            "page_no": page_no,
        }
        try:
            r = requests.get(f"{DART_BASE}/list.json", params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning(f"earnings list.json page {page_no} 실패: {e}")
            break
        if data.get("status") not in ("000", "013"):
            break
        items = data.get("list") or []
        if not items:
            break
        for it in items:
            nm = it.get("report_nm", "")
            if any(p in nm for p in EARNINGS_TITLE_PATTERNS):
                rows.append(it)
        total_page = data.get("total_page", page_no)
        if page_no >= total_page:
            break
        page_no += 1
    return rows


def _fetch_fields(rcept_no: str, api_key: str) -> dict[str, str]:
    url = f"{DART_BASE}/document.xml"
    try:
        r = requests.get(url, params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=20)
        r.raise_for_status()
        data = r.content
        if not data.startswith(b"PK"):
            return {}
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
        if not names:
            return {}
        raw = zf.open(names[0]).read()
        html = None
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                html = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not html:
            return {}
    except Exception as e:
        logger.warning(f"earnings document.xml {rcept_no} 실패: {e}")
        return {}

    fields: dict[str, str] = {}
    for m in FIELD_RE.finditer(html):
        fields[m.group(2).strip()] = m.group(3).strip()
    return fields


def _extract_earnings_numbers(fields: dict[str, str]) -> dict[str, float | None]:
    """매출액·영업이익·당기순이익 추출 — 라벨 변형 다수 수용."""
    revenue = None
    op = None
    net = None
    for label, val in fields.items():
        norm = label.replace(" ", "")
        if revenue is None and ("매출액" in norm or "영업수익" in norm):
            revenue = _parse_num(val)
        elif op is None and "영업이익" in norm:
            op = _parse_num(val)
        elif net is None and ("당기순이익" in norm or "순이익" == norm):
            net = _parse_num(val)
    return {"revenue": revenue, "op_profit": op, "net_profit": net}


async def collect_earnings(days_back: int = 14) -> dict:
    """최근 N일 공정공시 중 잠정/확정실적 수집 → EarningsEvent upsert."""
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        return {"status": "no_api_key"}

    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days_back)).strftime("%Y%m%d")

    loop = asyncio.get_event_loop()
    filings = await loop.run_in_executor(None, _fetch_list, bgn_de, end_de, api_key)
    logger.info(f"earnings filings: {len(filings)}건 (최근 {days_back}일)")

    if not filings:
        return {"status": "ok", "inserted": 0, "updated": 0, "total": 0}

    # 각 공시 본문 파싱 (병렬)
    sem = asyncio.Semaphore(3)

    async def _one(item: dict) -> dict | None:
        ticker = (item.get("stock_code") or "").strip()
        if not ticker:
            return None
        rcept_dt = item.get("rcept_dt", "")
        rcept_date = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}" if len(rcept_dt) == 8 else rcept_dt
        quarter = _derive_quarter(item.get("report_nm", "")) or "unknown"
        async with sem:
            fields = await loop.run_in_executor(None, _fetch_fields, item.get("rcept_no", ""), api_key)
        nums = _extract_earnings_numbers(fields)
        return {
            "ticker": ticker,
            "quarter": quarter,
            "scheduled_date": rcept_date,
            "reported_date": rcept_date,
            **nums,
        }

    results = await asyncio.gather(*[_one(f) for f in filings])
    events = [r for r in results if r]

    # DB upsert (SQLAlchemy)
    from sqlalchemy import select
    from app.database import async_session
    from app.models.tables import EarningsEvent

    inserted = 0
    updated = 0
    async with async_session() as db:
        for e in events:
            res = await db.execute(
                select(EarningsEvent).where(
                    EarningsEvent.ticker == e["ticker"],
                    EarningsEvent.quarter == e["quarter"],
                )
            )
            row = res.scalar_one_or_none()
            if row:
                row.reported_date = e["reported_date"]
                row.revenue = e["revenue"]
                row.op_profit = e["op_profit"]
                row.net_profit = e["net_profit"]
                updated += 1
            else:
                db.add(EarningsEvent(
                    id=secrets.token_hex(6),
                    ticker=e["ticker"],
                    quarter=e["quarter"],
                    scheduled_date=e["scheduled_date"],
                    reported_date=e["reported_date"],
                    revenue=e["revenue"],
                    op_profit=e["op_profit"],
                    net_profit=e["net_profit"],
                    source="dart",
                ))
                inserted += 1
        await db.commit()
    logger.info(f"earnings: {inserted} inserted, {updated} updated (총 {len(events)})")
    return {"status": "ok", "inserted": inserted, "updated": updated, "total": len(events)}

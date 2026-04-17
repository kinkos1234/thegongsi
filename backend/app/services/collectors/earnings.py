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

# 본문 표에서 "매출액" 같은 항목 라벨 span. 일부 공시는 "N. 매출액" 번호
# 접두가 붙지만, 실제 다수는 번호 없이 그냥 라벨만 있음("연결재무제표기준
# 영업(잠정)실적" 양식) — 번호는 optional.
LABEL_RE = re.compile(
    r'<span[^>]*>\s*(?:\d+\.\s*)?(매출액|영업이익|당기순이익|영업수익|순이익)\s*</span>',
    re.DOTALL,
)

# "당해실적" 바로 뒤에 오는 첫 xforms_input span = 이번 분기 실적값.
# DART 잠정실적 양식은 같은 행에 당해실적/전년동기/증감율/흑자적자/누계 5개 컬럼
# 이 연속하는데, 첫 xforms_input이 당해실적 값.
XFORMS_RE = re.compile(
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


def _derive_quarter(report_nm: str, rcept_ymd: str = "") -> str:
    """report_nm에 분기가 명시돼 있으면 우선, 아니면 접수일 기준 휴리스틱."""
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
    # rcept_dt 휴리스틱 — "연결재무제표기준영업(잠정)실적(공정공시)" 양식은
    # report_nm에 분기가 없고 접수일(보통 분기 종료 후 45일 이내)로 추정.
    if len(rcept_ymd) == 8 and rcept_ymd.isdigit():
        year = int(rcept_ymd[:4])
        month = int(rcept_ymd[4:6])
        # 월→분기 매핑 (대부분의 한국 상장사가 이 시점에 잠정실적 발표)
        if month in (1, 2, 3):
            return f"{year - 1}-Q4"
        if month in (4, 5, 6):
            return f"{year}-Q1"
        if month in (7, 8, 9):
            return f"{year}-Q2"
        if month in (10, 11, 12):
            return f"{year}-Q3"
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


def _fetch_document_html(rcept_no: str, api_key: str) -> str:
    """rcept_no 공시의 document.xml ZIP을 받아 안쪽 HTML 문자열 반환 (실패 시 '')."""
    url = f"{DART_BASE}/document.xml"
    try:
        r = requests.get(url, params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=20)
        r.raise_for_status()
        data = r.content
        if not data.startswith(b"PK"):
            return ""
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
        if not names:
            return ""
        raw = zf.open(names[0]).read()
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return ""
    except Exception as e:
        logger.warning(f"earnings document.xml {rcept_no} 실패: {e}")
        return ""


def _extract_earnings_numbers(html: str) -> dict[str, float | None]:
    """HTML에서 라벨(매출액/영업이익/당기순이익) 직후의 첫 xforms_input = 당해실적."""
    aliases = {"영업수익": "매출액", "순이익": "당기순이익"}
    results: dict[str, float | None] = {"매출액": None, "영업이익": None, "당기순이익": None}
    # 라벨을 발견하면, 해당 위치 이후의 첫 xforms_input을 당해실적으로 채택.
    # 같은 라벨이 여러 번 등장할 수 있음(표 중복) — 첫 non-null 값만 보관.
    for lbl_match in LABEL_RE.finditer(html):
        label = lbl_match.group(1)
        canonical = aliases.get(label, label)
        if results.get(canonical) is not None:
            continue
        # 라벨 바로 뒤 2KB 구간에서 첫 xforms_input 탐색 (보통 같은 <tr> 안)
        tail = html[lbl_match.end(): lbl_match.end() + 2000]
        val_match = XFORMS_RE.search(tail)
        if val_match:
            results[canonical] = _parse_num(val_match.group(1))
    return {
        "revenue": results["매출액"],
        "op_profit": results["영업이익"],
        "net_profit": results["당기순이익"],
    }


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
        quarter = _derive_quarter(item.get("report_nm", ""), rcept_dt) or "unknown"
        async with sem:
            html = await loop.run_in_executor(None, _fetch_document_html, item.get("rcept_no", ""), api_key)
        nums = _extract_earnings_numbers(html)
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

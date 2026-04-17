"""DART 공시 라우터."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Disclosure

router = APIRouter()


@router.get("/")
async def list_disclosures(
    ticker: str | None = None,
    severity: str | None = Query(None, description="high / med / low / uncertain"),
    q: str | None = Query(None, description="report_nm/summary_ko 부분일치"),
    form: str | None = Query(None, description="report_nm 정확일치 prefix (예: 유상증자결정)"),
    date_from: str | None = Query(None, description="YYYY-MM-DD 이상"),
    date_to: str | None = Query(None, description="YYYY-MM-DD 이하"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """공시 정밀검색.

    조합: ticker × severity × q(본문/제목 부분일치) × form(제목 prefix) × rcept_dt 범위.
    과거 공시 탐색 수요(Threads 피드백 대응).
    """
    query = select(Disclosure).order_by(Disclosure.rcept_dt.desc())
    if ticker:
        query = query.where(Disclosure.ticker == ticker)
    if severity:
        query = query.where(Disclosure.anomaly_severity == severity)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Disclosure.report_nm.ilike(pattern),
                func.coalesce(Disclosure.summary_ko, "").ilike(pattern),
            )
        )
    if form:
        query = query.where(Disclosure.report_nm.ilike(f"{form}%"))
    if date_from:
        query = query.where(Disclosure.rcept_dt >= date_from)
    if date_to:
        query = query.where(Disclosure.rcept_dt <= date_to)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return [
        {
            "rcept_no": d.rcept_no,
            "ticker": d.ticker,
            "title": d.report_nm,
            "date": d.rcept_dt,
            "summary": d.summary_ko,
            "severity": d.anomaly_severity,
            "reason": d.anomaly_reason,
            "raw_url": d.raw_url,
        }
        for d in result.scalars().all()
    ]


@router.get("/{rcept_no}/preview")
async def disclosure_preview(rcept_no: str, db: AsyncSession = Depends(get_db)):
    """공시 문서 핵심 필드 미리보기 — OpenDART document.xml 파싱.

    본문 HTML 표에서 `N. 라벨 → 값` 페어를 추출해 구조화된 JSON으로 반환.
    프론트는 iframe 없이 가벼운 모달로 렌더 (DART는 X-Frame-Options으로 iframe 차단).
    """
    res = await db.execute(select(Disclosure).where(Disclosure.rcept_no == rcept_no))
    disclosure = res.scalar_one_or_none()
    if not disclosure:
        raise HTTPException(status_code=404, detail="없는 공시입니다.")

    import asyncio as _asyncio
    import io
    import os
    import zipfile
    import requests

    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="DART_API_KEY 미설정")

    def _fetch_fields() -> dict:
        url = "https://opendart.fss.or.kr/api/document.xml"
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
        from app.services.calendar.dividend_dates import _extract_fields
        return _extract_fields(html)

    loop = _asyncio.get_event_loop()
    try:
        fields = await loop.run_in_executor(None, _fetch_fields)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"DART 조회 실패: {type(e).__name__}")

    return {
        "rcept_no": rcept_no,
        "ticker": disclosure.ticker,
        "title": disclosure.report_nm,
        "date": disclosure.rcept_dt,
        "summary_ko": disclosure.summary_ko,
        "fields": fields,
        "dart_url": disclosure.raw_url,
    }


@router.get("/count")
async def count_disclosures(
    ticker: str | None = None,
    q: str | None = None,
    form: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """검색 조건 적용 총 건수 (페이지네이션 UI용)."""
    query = select(func.count(Disclosure.id))
    if ticker:
        query = query.where(Disclosure.ticker == ticker)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Disclosure.report_nm.ilike(pattern),
                func.coalesce(Disclosure.summary_ko, "").ilike(pattern),
            )
        )
    if form:
        query = query.where(Disclosure.report_nm.ilike(f"{form}%"))
    if date_from:
        query = query.where(Disclosure.rcept_dt >= date_from)
    if date_to:
        query = query.where(Disclosure.rcept_dt <= date_to)
    result = await db.execute(query)
    return {"count": result.scalar_one()}

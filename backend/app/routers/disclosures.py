"""DART 공시 라우터."""
from fastapi import APIRouter, Depends, Query
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

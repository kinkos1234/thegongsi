"""DART 공시 라우터."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Disclosure

router = APIRouter()


@router.get("/")
async def list_disclosures(
    ticker: str | None = None,
    severity: str | None = Query(None, description="high / med / low / uncertain"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Disclosure).order_by(Disclosure.rcept_dt.desc())
    if ticker:
        query = query.where(Disclosure.ticker == ticker)
    if severity:
        query = query.where(Disclosure.anomaly_severity == severity)
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

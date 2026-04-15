"""DART 공시 라우터 (placeholder)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Disclosure

router = APIRouter()


@router.get("/")
async def list_disclosures(ticker: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Disclosure).order_by(Disclosure.rcept_dt.desc()).limit(50)
    if ticker:
        query = query.where(Disclosure.ticker == ticker)
    result = await db.execute(query)
    return [
        {
            "rcept_no": d.rcept_no,
            "ticker": d.ticker,
            "title": d.report_nm,
            "date": d.rcept_dt,
            "summary": d.summary_ko,
            "severity": d.anomaly_severity,
        }
        for d in result.scalars().all()
    ]

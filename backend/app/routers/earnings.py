"""실적 캘린더 라우터."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.market import Company
from app.models.tables import EarningsEvent

router = APIRouter()


@router.get("/")
async def list_events(
    ticker: str | None = None,
    upcoming: bool = True,
    db: AsyncSession = Depends(get_db),
):
    # companies LEFT JOIN 으로 종목명(name_ko) 함께 반환 — 프론트에서 티커만 보여주면
    # 직관성 떨어짐 (Threads 피드백 반영, 2026-04-18).
    query = select(EarningsEvent, Company.name_ko).outerjoin(Company, Company.ticker == EarningsEvent.ticker)
    if ticker:
        query = query.where(EarningsEvent.ticker == ticker)
    if upcoming:
        from datetime import date
        today = date.today().isoformat()
        query = query.where(EarningsEvent.scheduled_date >= today)
        query = query.order_by(EarningsEvent.scheduled_date.asc())
    else:
        query = query.order_by(EarningsEvent.reported_date.desc(), EarningsEvent.scheduled_date.desc())
    query = query.limit(50)
    result = await db.execute(query)
    rows = result.all()
    return [
        {
            "ticker": e.ticker,
            "name": name,
            "quarter": e.quarter,
            "scheduled": e.scheduled_date,
            "reported": e.reported_date,
            "revenue": e.revenue,
            "op_profit": e.op_profit,
            "net_profit": e.net_profit,
        }
        for e, name in rows
    ]

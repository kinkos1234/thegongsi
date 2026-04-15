"""실적 캘린더 라우터."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import EarningsEvent

router = APIRouter()


@router.get("/")
async def list_events(
    ticker: str | None = None,
    upcoming: bool = True,
    db: AsyncSession = Depends(get_db),
):
    query = select(EarningsEvent).order_by(EarningsEvent.scheduled_date.asc()).limit(50)
    if ticker:
        query = query.where(EarningsEvent.ticker == ticker)
    if upcoming:
        from datetime import date
        today = date.today().isoformat()
        query = query.where(EarningsEvent.scheduled_date >= today)
    result = await db.execute(query)
    return [
        {
            "ticker": e.ticker,
            "quarter": e.quarter,
            "scheduled": e.scheduled_date,
            "reported": e.reported_date,
            "revenue": e.revenue,
            "op_profit": e.op_profit,
            "net_profit": e.net_profit,
        }
        for e in result.scalars().all()
    ]

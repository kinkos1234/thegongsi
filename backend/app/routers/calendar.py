"""권리락·배당락·지급일 캘린더 API."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import CalendarEvent, Company

router = APIRouter()


@router.get("/upcoming")
async def upcoming_events(
    days: int = Query(7, ge=1, le=60, description="오늘부터 N일 이내 이벤트"),
    event_type: str | None = Query(None, description="ex_right | ex_dividend | record_date | payment_date"),
    db: AsyncSession = Depends(get_db),
):
    """오늘로부터 days 이내 예정된 ex-date 이벤트.

    프론트 D-7 캘린더 위젯용. ticker + 종목명 병기.
    """
    today = date.today().isoformat()
    end = (date.today() + timedelta(days=days)).isoformat()

    conds = [CalendarEvent.event_date >= today, CalendarEvent.event_date <= end]
    if event_type:
        conds.append(CalendarEvent.event_type == event_type)

    q = (
        select(CalendarEvent, Company.name_ko)
        .outerjoin(Company, Company.ticker == CalendarEvent.ticker)
        .where(and_(*conds))
        .order_by(CalendarEvent.event_date.asc(), CalendarEvent.ticker.asc())
        .limit(200)
    )
    result = await db.execute(q)
    return [
        {
            "ticker": ev.ticker,
            "name": name,
            "event_type": ev.event_type,
            "event_date": ev.event_date,
            "rcept_no": ev.rcept_no,
            "title": ev.title,
        }
        for ev, name in result.all()
    ]


@router.get("/ticker/{ticker}")
async def ticker_events(
    ticker: str,
    upcoming_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """특정 종목의 최근/예정 이벤트 (최대 20건)."""
    q = select(CalendarEvent).where(CalendarEvent.ticker == ticker)
    if upcoming_only:
        q = q.where(CalendarEvent.event_date >= date.today().isoformat())
    q = q.order_by(CalendarEvent.event_date.asc()).limit(20)
    result = await db.execute(q)
    return [
        {
            "event_type": ev.event_type,
            "event_date": ev.event_date,
            "rcept_no": ev.rcept_no,
            "title": ev.title,
        }
        for ev in result.scalars().all()
    ]

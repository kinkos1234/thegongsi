"""권리락·배당락·지급일 캘린더 API.

Dedup 규칙: (ticker, event_type, event_date) 중복 시 rcept_no 가장 큰(=최신)
것 1건만 노출. 기재정정 공시가 여러 번 나와 같은 날 이벤트가 중복 들어오는
케이스(예: 044480 2026-04-20 payment_date) 에서 프론트에 중복 표시되던
문제 방지.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import CalendarEvent, Company

router = APIRouter()


def _dedup_subq(conds):
    """(ticker, event_type, event_date) 그룹별 max(rcept_no) 서브쿼리.

    rcept_no 는 YYYYMMDDnnnnnnn 포맷의 문자열이라 lexicographic max ==
    시간순 최신. 기재정정 공시(정정사유·발행조건확정) 우선 노출.
    """
    return (
        select(
            CalendarEvent.ticker.label("ticker"),
            CalendarEvent.event_type.label("event_type"),
            CalendarEvent.event_date.label("event_date"),
            func.max(CalendarEvent.rcept_no).label("max_rcept"),
        )
        .where(and_(*conds))
        .group_by(
            CalendarEvent.ticker,
            CalendarEvent.event_type,
            CalendarEvent.event_date,
        )
        .subquery()
    )


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

    dedup = _dedup_subq(conds)
    q = (
        select(CalendarEvent, Company.name_ko)
        .join(
            dedup,
            and_(
                CalendarEvent.ticker == dedup.c.ticker,
                CalendarEvent.event_type == dedup.c.event_type,
                CalendarEvent.event_date == dedup.c.event_date,
                CalendarEvent.rcept_no == dedup.c.max_rcept,
            ),
        )
        .outerjoin(Company, Company.ticker == CalendarEvent.ticker)
        .where(and_(*conds))
        .order_by(CalendarEvent.event_date.asc(), CalendarEvent.ticker.asc())
        .limit(500)
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
    conds = [CalendarEvent.ticker == ticker]
    if upcoming_only:
        conds.append(CalendarEvent.event_date >= date.today().isoformat())

    dedup = _dedup_subq(conds)
    q = (
        select(CalendarEvent)
        .join(
            dedup,
            and_(
                CalendarEvent.ticker == dedup.c.ticker,
                CalendarEvent.event_type == dedup.c.event_type,
                CalendarEvent.event_date == dedup.c.event_date,
                CalendarEvent.rcept_no == dedup.c.max_rcept,
            ),
        )
        .where(and_(*conds))
        .order_by(CalendarEvent.event_date.asc())
        .limit(20)
    )
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

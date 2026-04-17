import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Company, User, WatchListItem
from app.routers import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


async def _backfill_task(ticker: str, days: int, user_id: str | None = None):
    """watchlist 추가 시 백그라운드 실행 — DART 공시 N일치 + anomaly + DD 메모 자동 생성."""
    from app.services.collectors.dart import backfill_ticker
    try:
        result = await backfill_ticker(ticker, days=days)
        logger.info(f"watchlist backfill {ticker}: {result}")
    except Exception as e:
        logger.exception(f"watchlist backfill {ticker} failed: {e}")
        return

    # 공시 수집 성공 후 후속 작업 체인
    if result.get("status") == "ok" and result.get("inserted", 0) >= 0:
        # (1) 권리락·배당락 이벤트 스캔 + 저장
        try:
            import asyncpg
            import os
            from app.services.calendar.ex_dates import scan_ex_dates, upsert_events
            corp_code = result.get("corp_code", "")
            if corp_code:
                events = await scan_ex_dates([(ticker, corp_code)], days_back=180, concurrency=3)
                if events:
                    url = os.environ.get("DATABASE_URL", "")
                    for p in ("postgresql+asyncpg://", "postgres+asyncpg://"):
                        if url.startswith(p):
                            url = url.replace(p, "postgresql://", 1)
                            break
                    conn = await asyncpg.connect(url)
                    try:
                        await upsert_events(conn, events)
                        logger.info(f"watchlist calendar {ticker}: +{len(events)} events")
                    finally:
                        await conn.close()
        except Exception as e:
            logger.warning(f"watchlist calendar {ticker} skipped: {e}")

        # (2) DD 메모 자동 생성
        try:
            from app.services.memo.generator import generate_memo
            memo_result = await generate_memo(ticker, user_id=user_id)
            logger.info(f"watchlist auto-memo {ticker}: version={memo_result.get('version')}")
        except Exception as e:
            logger.warning(f"watchlist auto-memo {ticker} skipped: {e}")


class AddRequest(BaseModel):
    ticker: str
    backfill_days: int = Field(90, ge=0, le=365, description="공시 백필 기간 (0=비활성, 최대 1년)")


@router.get("/")
async def list_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Watchlist + Company.name_ko 병기 (LEFT JOIN, 이름 없으면 null)."""
    result = await db.execute(
        select(WatchListItem, Company.name_ko, Company.market)
        .outerjoin(Company, Company.ticker == WatchListItem.ticker)
        .where(WatchListItem.user_id == user.id)
        .order_by(WatchListItem.added_at.desc())
    )
    return [
        {
            "ticker": item.ticker,
            "name": name or None,
            "market": market or None,
            "added_at": item.added_at.isoformat(),
        }
        for item, name, market in result.all()
    ]


@router.post("/")
async def add_watchlist(
    req: AddRequest,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(WatchListItem).where(WatchListItem.user_id == user.id, WatchListItem.ticker == req.ticker)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 추가된 종목입니다.")
    item = WatchListItem(user_id=user.id, ticker=req.ticker)
    db.add(item)
    await db.commit()

    # 백그라운드: 최근 N일 공시 백필 + anomaly scan + DD 메모 자동 생성
    backfill_status = "skipped"
    if req.backfill_days > 0:
        background.add_task(_backfill_task, req.ticker, req.backfill_days, user.id)
        backfill_status = f"queued_{req.backfill_days}d"

    return {"ticker": req.ticker, "status": "added", "backfill": backfill_status}


@router.delete("/{ticker}")
async def remove_watchlist(ticker: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WatchListItem).where(WatchListItem.user_id == user.id, WatchListItem.ticker == ticker)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="없는 종목입니다.")
    await db.delete(item)
    await db.commit()
    return {"status": "removed"}

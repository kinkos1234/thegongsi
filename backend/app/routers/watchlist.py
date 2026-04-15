import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import User, WatchListItem
from app.routers import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


async def _backfill_task(ticker: str, days: int):
    """watchlist 추가 시 백그라운드 실행 — DART 공시 N일치 + anomaly scan."""
    from app.services.collectors.dart import backfill_ticker
    try:
        result = await backfill_ticker(ticker, days=days)
        logger.info(f"watchlist backfill {ticker}: {result}")
    except Exception as e:
        logger.exception(f"watchlist backfill {ticker} failed: {e}")


class AddRequest(BaseModel):
    ticker: str
    backfill_days: int = Field(90, ge=0, le=365, description="공시 백필 기간 (0=비활성, 최대 1년)")


@router.get("/")
async def list_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchListItem).where(WatchListItem.user_id == user.id))
    return [{"ticker": i.ticker, "added_at": i.added_at.isoformat()} for i in result.scalars().all()]


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

    # 백그라운드: 최근 N일 공시 백필 + anomaly scan (blocking 없이)
    backfill_status = "skipped"
    if req.backfill_days > 0:
        background.add_task(_backfill_task, req.ticker, req.backfill_days)
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

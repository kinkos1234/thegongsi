from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import User, WatchListItem
from app.routers import get_current_user

router = APIRouter()


class AddRequest(BaseModel):
    ticker: str


@router.get("/")
async def list_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchListItem).where(WatchListItem.user_id == user.id))
    return [{"ticker": i.ticker, "added_at": i.added_at.isoformat()} for i in result.scalars().all()]


@router.post("/")
async def add_watchlist(req: AddRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(WatchListItem).where(WatchListItem.user_id == user.id, WatchListItem.ticker == req.ticker)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 추가된 종목입니다.")
    item = WatchListItem(user_id=user.id, ticker=req.ticker)
    db.add(item)
    await db.commit()
    return {"ticker": req.ticker, "status": "added"}


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

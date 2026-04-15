"""AI DD 메모 라우터 (placeholder)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import DDMemo
from app.routers import get_current_user_optional

router = APIRouter()


class GenerateRequest(BaseModel):
    ticker: str


@router.post("/generate")
async def generate_memo(req: GenerateRequest, user=Depends(get_current_user_optional)):
    from app.services.memo.generator import generate_memo as _gen
    user_id = user.id if user else None
    return await _gen(req.ticker, user_id=user_id)


@router.get("/{ticker}")
async def get_latest_memo(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DDMemo).where(DDMemo.ticker == ticker).order_by(DDMemo.created_at.desc()).limit(1)
    )
    memo = result.scalar_one_or_none()
    return {"memo_id": memo.id if memo else None}

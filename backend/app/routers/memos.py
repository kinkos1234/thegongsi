"""AI DD 메모 라우터."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import DDMemo, DDMemoVersion
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
    """Ticker의 최신 DD 메모 (없으면 404)."""
    memo_res = await db.execute(
        select(DDMemo).where(DDMemo.ticker == ticker).order_by(DDMemo.created_at.desc()).limit(1)
    )
    memo = memo_res.scalar_one_or_none()
    if not memo or not memo.latest_version_id:
        raise HTTPException(status_code=404, detail="아직 생성된 DD 메모가 없습니다.")

    ver_res = await db.execute(
        select(DDMemoVersion).where(DDMemoVersion.id == memo.latest_version_id)
    )
    ver = ver_res.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail="메모 버전을 찾을 수 없습니다.")
    return {
        "memo_id": memo.id,
        "version_id": ver.id,
        "version": ver.version,
        "bull": ver.bull,
        "bear": ver.bear,
        "thesis": ver.thesis,
    }

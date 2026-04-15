"""AI DD 메모 라우터."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import DDMemo, DDMemoVersion
from app.routers import get_current_user

router = APIRouter()


class GenerateRequest(BaseModel):
    ticker: str


@router.post("/generate")
async def generate_memo(req: GenerateRequest, user=Depends(get_current_user)):
    """인증 필수. BYOK 우선, 없으면 서버 키 fallback(일일 쿼터)."""
    from app.services.memo.generator import generate_memo as _gen
    try:
        return await _gen(req.ticker, user_id=user.id)
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith("quota_exceeded"):
            raise HTTPException(status_code=429, detail=msg)
        raise HTTPException(status_code=503, detail=msg)


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

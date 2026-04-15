"""사용자 피드백 라우터 (Fei-Fei human-in-the-loop)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import DisclosureFeedback, MemoFeedback
from app.routers import get_current_user_optional

router = APIRouter()


class DiscFeedbackRequest(BaseModel):
    rcept_no: str
    rating: int = Field(ge=-1, le=1)
    reason: str | None = None


class MemoFeedbackRequest(BaseModel):
    memo_version_id: str
    rating: int = Field(ge=-1, le=1)
    reason: str | None = None


@router.post("/disclosure")
async def disclosure_feedback(
    req: DiscFeedbackRequest,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    db.add(DisclosureFeedback(
        user_id=user.id if user else None,
        rcept_no=req.rcept_no,
        rating=req.rating,
        reason=req.reason,
    ))
    await db.commit()
    return {"status": "recorded"}


@router.post("/memo")
async def memo_feedback(
    req: MemoFeedbackRequest,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    db.add(MemoFeedback(
        user_id=user.id if user else None,
        memo_version_id=req.memo_version_id,
        rating=req.rating,
        reason=req.reason,
    ))
    await db.commit()
    return {"status": "recorded"}

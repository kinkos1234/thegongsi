"""GraphRAG 자연어 Q&A 라우터 — 인증 필수 (BYOK 우선)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers import get_current_user

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@router.post("/ask")
async def ask(req: AskRequest, user=Depends(get_current_user)):
    """인증 필수. user의 BYOK 우선, 없으면 서버 키(호스트 관리자 소유) fallback."""
    from app.services.graph.qa import ask as _ask
    try:
        return await _ask(req.question, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith("quota_exceeded"):
            raise HTTPException(status_code=429, detail=msg)
        raise HTTPException(status_code=503, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GraphRAG 실행 실패: {e}")

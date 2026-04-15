"""GraphRAG 자연어 Q&A 라우터 (BYOK 지원)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers import get_current_user_optional

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@router.post("/ask")
async def ask(req: AskRequest, user=Depends(get_current_user_optional)):
    """로그인 사용자는 BYOK 우선 사용, 비로그인은 서버 키 폴백."""
    from app.services.graph.qa import ask as _ask
    try:
        return await _ask(req.question, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GraphRAG 실행 실패: {e}")

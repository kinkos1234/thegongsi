"""Graph management endpoints (관리자/개발용). 인증 필수."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.routers import get_current_user
from app.config import settings

router = APIRouter()


def _require_admin(user):
    """ADMIN_EMAILS에 포함된 사용자만 허용."""
    if user.email.lower() not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="Admin only")


class ExtractRequest(BaseModel):
    ticker: str


@router.post("/extract-governance")
async def extract_governance(req: ExtractRequest, user=Depends(get_current_user)):
    """Ticker의 지배구조 공시에서 인물 추출 → Neo4j upsert."""
    _require_admin(user)
    from app.services.graph.extractor import extract_from_disclosures
    try:
        return await extract_from_disclosures(req.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추출 실패: {e}")


class SyncRequest(BaseModel):
    tickers: list[str] | None = None
    limit: int = 500


@router.post("/sync-disclosures")
async def sync_disclosures_endpoint(req: SyncRequest, user=Depends(get_current_user)):
    """수동 Postgres → Neo4j 공시 sync."""
    _require_admin(user)
    from app.services.graph.sync import sync_disclosures
    try:
        return await sync_disclosures(tickers=req.tickers, limit=req.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sync 실패: {e}")

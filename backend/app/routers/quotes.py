"""시세 조회 라우터."""
from fastapi import APIRouter, HTTPException, Query

from app.services.quotes import get_quote

router = APIRouter()


@router.get("/{ticker}")
async def quote(ticker: str, refresh: bool = Query(False, description="캐시 무시")):
    try:
        return await get_quote(ticker, force=refresh)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"시세 조회 실패: {e}")

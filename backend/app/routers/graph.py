"""Graph management endpoints (관리자/개발용)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ExtractRequest(BaseModel):
    ticker: str


@router.post("/extract-governance")
async def extract_governance(req: ExtractRequest):
    """Ticker의 지배구조 공시에서 인물 추출 → Neo4j upsert."""
    from app.services.graph.extractor import extract_from_disclosures
    try:
        return await extract_from_disclosures(req.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추출 실패: {e}")


class SyncRequest(BaseModel):
    tickers: list[str] | None = None
    limit: int = 500


@router.post("/sync-disclosures")
async def sync_disclosures_endpoint(req: SyncRequest):
    """수동 Postgres → Neo4j 공시 sync."""
    from app.services.graph.sync import sync_disclosures
    try:
        return await sync_disclosures(tickers=req.tickers, limit=req.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sync 실패: {e}")

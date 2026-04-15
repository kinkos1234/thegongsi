"""종목 대시보드 라우터 (placeholder — Phase 1 구현 예정)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Company

router = APIRouter()


@router.get("/{ticker}")
async def get_company(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    return {
        "ticker": company.ticker,
        "name": company.name_ko,
        "market": company.market,
        "sector": company.sector,
        "price": company.current_price,
        "change": company.change_percent,
    }

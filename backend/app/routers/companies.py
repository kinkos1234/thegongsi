"""종목 대시보드 라우터."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Company, Disclosure

router = APIRouter()


@router.get("/")
async def list_companies(
    q: str | None = Query(None, description="ticker/name_ko/sector 검색"),
    market: str | None = Query(None, description="KOSPI / KOSDAQ"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Company 목록. 검색어 q 있으면 ticker/이름/섹터 부분일치."""
    query = select(Company)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                Company.ticker.ilike(pattern),
                func.lower(Company.name_ko).like(pattern),
                func.lower(func.coalesce(Company.sector, "")).like(pattern),
            )
        )
    if market:
        query = query.where(Company.market == market)
    query = query.order_by(Company.ticker).offset(offset).limit(limit)
    result = await db.execute(query)
    return [
        {
            "ticker": c.ticker,
            "name": c.name_ko,
            "market": c.market,
            "sector": c.sector,
            "price": c.current_price,
            "change": c.change_percent,
        }
        for c in result.scalars().all()
    ]


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


@router.get("/{ticker}/today-anomalies")
async def today_anomalies(ticker: str, db: AsyncSession = Depends(get_db)):
    """Ticker의 최근 7일 내 high/med severity 공시 수."""
    from datetime import datetime, timedelta, timezone
    KST = timezone(timedelta(hours=9))
    since = (datetime.now(KST) - timedelta(days=7)).strftime("%Y-%m-%d")
    result = await db.execute(
        select(Disclosure)
        .where(
            Disclosure.ticker == ticker,
            Disclosure.rcept_dt >= since,
            Disclosure.anomaly_severity.in_(["high", "med"]),
        )
        .order_by(Disclosure.rcept_dt.desc())
    )
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "high": sum(1 for d in rows if d.anomaly_severity == "high"),
        "med": sum(1 for d in rows if d.anomaly_severity == "med"),
        "items": [
            {
                "rcept_no": d.rcept_no,
                "title": d.report_nm,
                "date": d.rcept_dt,
                "severity": d.anomaly_severity,
            }
            for d in rows[:3]
        ],
    }

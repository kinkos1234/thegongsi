"""종목 대시보드 라우터."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import (
    Company,
    CorporateOwnership,
    Disclosure,
    ShortSellingSnapshot,
)

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


@router.get("/{ticker}/related")
async def related_companies(
    ticker: str,
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Ticker 중심 관계 그래프 — ownership 우선, sector 보완.

    반환:
    - center: 중심 기업
    - peers: [{ ticker, name, sector, change, relation, stake_pct?, direction? }]
    - relations: {relation_type: count}

    relation 종류:
    - parent: 이 회사를 보유한 법인
    - child: 이 회사가 보유한 법인
    - sector: 같은 섹터 (ownership 관계 없는 동종)
    """
    res = await db.execute(select(Company).where(Company.ticker == ticker))
    center = res.scalar_one_or_none()
    if not center:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")

    peers: list[dict] = []
    used_tickers: set[str] = {ticker}

    # 1) 부모 (parent: 이 회사 주식을 보유한 법인)
    parents_res = await db.execute(
        select(CorporateOwnership)
        .where(CorporateOwnership.child_ticker == ticker)
        .order_by(CorporateOwnership.stake_pct.desc().nullslast())
        .limit(limit)
    )
    for p in parents_res.scalars().all():
        if p.parent_ticker in used_tickers:
            continue
        used_tickers.add(p.parent_ticker)
        peer = await _fetch_peer(db, p.parent_ticker, fallback_name=p.parent_name)
        peer["relation"] = "parent"
        peer["stake_pct"] = p.stake_pct
        peer["direction"] = "in"
        peers.append(peer)
        if len(peers) >= limit:
            break

    # 2) 자식 (child: 이 회사가 보유한 법인)
    if len(peers) < limit:
        children_res = await db.execute(
            select(CorporateOwnership)
            .where(CorporateOwnership.parent_ticker == ticker)
            .order_by(CorporateOwnership.stake_pct.desc().nullslast())
            .limit(limit - len(peers))
        )
        for c in children_res.scalars().all():
            if c.child_ticker in used_tickers:
                continue
            used_tickers.add(c.child_ticker)
            peer = await _fetch_peer(db, c.child_ticker, fallback_name=c.child_name)
            peer["relation"] = "child"
            peer["stake_pct"] = c.stake_pct
            peer["direction"] = "out"
            peers.append(peer)
            if len(peers) >= limit:
                break

    # 3) 섹터 피어 (ownership 없는 자리 채우기)
    if len(peers) < limit and center.sector:
        sector_res = await db.execute(
            select(Company)
            .where(Company.sector == center.sector, Company.ticker != ticker)
            .order_by(Company.ticker)
            .limit(limit - len(peers))
        )
        for co in sector_res.scalars().all():
            if co.ticker in used_tickers:
                continue
            used_tickers.add(co.ticker)
            peer = _company_brief(co)
            peer["relation"] = "sector"
            peers.append(peer)
            if len(peers) >= limit:
                break

    # 집계
    counts: dict[str, int] = {}
    for p in peers:
        counts[p["relation"]] = counts.get(p["relation"], 0) + 1
    primary = "ownership" if (counts.get("parent", 0) + counts.get("child", 0)) > 0 else "sector"

    return {
        "center": _company_brief(center),
        "relation": primary,
        "relations": counts,
        "peers": peers,
    }


async def _fetch_peer(db: AsyncSession, ticker: str, fallback_name: str | None = None) -> dict:
    res = await db.execute(select(Company).where(Company.ticker == ticker))
    co = res.scalar_one_or_none()
    if co:
        return _company_brief(co)
    return {
        "ticker": ticker,
        "name": fallback_name or ticker,
        "sector": None,
        "change": None,
    }


def _company_brief(c: Company) -> dict:
    return {
        "ticker": c.ticker,
        "name": c.name_ko,
        "sector": c.sector,
        "change": c.change_percent,
    }


@router.get("/{ticker}/governance")
async def governance(ticker: str, db: AsyncSession = Depends(get_db)):
    """Ticker의 지배구조 스냅샷 — 최대주주·임원·모자회사·순환고리.

    SQL 스냅샷 테이블(`MajorShareholder`/`Insider`/`CorporateOwnership`)을 조회.
    순환출자는 SQL DFS로 탐지 (Neo4j fallback). 데이터 없으면 빈 섹션 반환.
    """
    from app.services.graph.governance_query import (
        detect_circular_ownership_sql,
        governance_snapshot,
    )

    snap = await governance_snapshot(ticker, db)
    cycles = await detect_circular_ownership_sql(ticker, db)
    snap["cycles"] = cycles
    return snap


@router.get("/{ticker}/short-selling")
async def short_selling_series(
    ticker: str,
    days: int = Query(30, ge=7, le=120),
    db: AsyncSession = Depends(get_db),
):
    """Ticker의 최근 N일 공매도 비중 시계열 — 한국 시장 고유 시각."""
    res = await db.execute(
        select(ShortSellingSnapshot)
        .where(ShortSellingSnapshot.ticker == ticker)
        .order_by(ShortSellingSnapshot.date.desc())
        .limit(days)
    )
    rows = list(res.scalars().all())
    rows.reverse()
    series = [
        {
            "date": r.date,
            "ratio": r.ratio,
            "volume": r.volume,
        }
        for r in rows
    ]
    return {"ticker": ticker, "days": days, "series": series}


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

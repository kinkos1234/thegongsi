"""종목 대시보드 라우터."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import (
    Company,
    CorporateOwnership,
    Disclosure,
    GovernanceExtractRequest,
    Insider,
    MajorShareholder,
    ShortSellingSnapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    used_names: set[str] = {center.name_ko.strip().lower()}

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
        peer_name = str(peer.get("name") or "").strip().lower()
        if peer_name and peer_name in used_names:
            continue
        if peer_name:
            used_names.add(peer_name)
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
            peer_name = str(peer.get("name") or "").strip().lower()
            if peer_name and peer_name in used_names:
                continue
            if peer_name:
                used_names.add(peer_name)
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
            peer_name = co.name_ko.strip().lower()
            if peer_name in used_names:
                continue
            used_tickers.add(co.ticker)
            used_names.add(peer_name)
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


# ─── Phase 3: user-triggered governance extraction ─────────────────────────
# 워치리스트에 없는 "콜드" 종목을 사용자가 열람했을 때, 스스로 "AI 추출 시작"
# 버튼을 눌러 governance 스냅샷을 채울 수 있게 한다. Anthropic 비용 보호를
# 위한 다층 가드:
#   - 이미 추출된 ticker: 즉시 거절 (비용 0)
#   - ticker당 1시간 내 시도 1회: 쿨다운 (중복 트리거 방지)
#   - IP당 시간당 3회, 일 10회: rate limit (크롤러/악용 방지)
# 요청 로그(GovernanceExtractRequest)는 추적·감사용 영구 보존.

_TICKER_COOLDOWN_MIN = 60  # ticker 단위 쿨다운
_IP_HOUR_LIMIT = 3          # IP당 시간당
_IP_DAY_LIMIT = 10          # IP당 일


async def _has_governance_data(ticker: str, db: AsyncSession) -> bool:
    r = await db.execute(select(MajorShareholder.id).where(MajorShareholder.ticker == ticker).limit(1))
    if r.first():
        return True
    r = await db.execute(select(Insider.id).where(Insider.ticker == ticker).limit(1))
    if r.first():
        return True
    r = await db.execute(
        select(CorporateOwnership.id)
        .where(
            or_(
                CorporateOwnership.parent_ticker == ticker,
                CorporateOwnership.child_ticker == ticker,
            )
        )
        .limit(1)
    )
    return r.first() is not None


def _client_ip(request: Request) -> str:
    # Fly / reverse proxy 환경: X-Forwarded-For 맨 앞이 실제 클라이언트.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


@router.post("/{ticker}/governance/extract")
async def extract_governance_on_demand(
    ticker: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """사용자가 "AI 지배구조 추출" 버튼 눌렀을 때의 퍼블릭 엔드포인트.

    동기 실행: 호출 즉시 DART fetch + LLM 추출(20-60초) 후 결과 반환.
    큐 + 워커 구조 대신 인라인으로 처리 — Fly auto-start + Actions 동일 패턴.

    쿨다운/리밋에 걸리면 `status`에 사유, `next_eligible_at`(UTC ISO) 반환.
    """
    company_r = await db.execute(select(Company).where(Company.ticker == ticker))
    if not company_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="ticker not found")

    if await _has_governance_data(ticker, db):
        return {"status": "already_extracted", "ticker": ticker}

    ip = _client_ip(request)
    now = _utc_now()

    # 1) ticker 쿨다운
    last_ticker_r = await db.execute(
        select(GovernanceExtractRequest)
        .where(
            GovernanceExtractRequest.ticker == ticker,
            GovernanceExtractRequest.requested_at > now - timedelta(minutes=_TICKER_COOLDOWN_MIN),
        )
        .order_by(GovernanceExtractRequest.requested_at.desc())
        .limit(1)
    )
    last_ticker = last_ticker_r.scalar_one_or_none()
    if last_ticker is not None:
        next_eligible = last_ticker.requested_at + timedelta(minutes=_TICKER_COOLDOWN_MIN)
        return {
            "status": "cooldown",
            "ticker": ticker,
            "last_status": last_ticker.status,
            "next_eligible_at": next_eligible.isoformat() + "Z",
        }

    # 2) IP rate limit
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    ip_hour_r = await db.execute(
        select(func.count())
        .select_from(GovernanceExtractRequest)
        .where(
            GovernanceExtractRequest.requester_ip == ip,
            GovernanceExtractRequest.requested_at > hour_ago,
        )
    )
    ip_hour = ip_hour_r.scalar_one()
    ip_day_r = await db.execute(
        select(func.count())
        .select_from(GovernanceExtractRequest)
        .where(
            GovernanceExtractRequest.requester_ip == ip,
            GovernanceExtractRequest.requested_at > day_ago,
        )
    )
    ip_day = ip_day_r.scalar_one()
    if ip_hour >= _IP_HOUR_LIMIT or ip_day >= _IP_DAY_LIMIT:
        return {
            "status": "ip_limit",
            "ticker": ticker,
            "ip_hour": ip_hour,
            "ip_day": ip_day,
            "limits": {"per_hour": _IP_HOUR_LIMIT, "per_day": _IP_DAY_LIMIT},
        }

    # 3) 실행
    req = GovernanceExtractRequest(
        ticker=ticker, status="processing", requester_ip=ip,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    from app.services.graph.extractor import extract_from_disclosures
    try:
        result = await extract_from_disclosures(ticker)
        st = result.get("status", "done")
        # no_governance_disclosures → 'no_data'로 정규화
        norm = "no_data" if st in ("no_governance_disclosures",) else (
            "done" if st == "ok" else st
        )
        req.status = norm
        req.finished_at = _utc_now()
        req.result_summary = (
            f"persons={result.get('persons_upserted', 0)} "
            f"corps={result.get('corps_upserted', 0)}"
        )[:200]
        await db.commit()
        return {"status": norm, "ticker": ticker, "result": result}
    except Exception as e:
        logger.exception("on-demand governance extract failed for %s", ticker)
        req.status = "failed"
        req.finished_at = _utc_now()
        req.error = f"{type(e).__name__}: {e}"[:500]
        await db.commit()
        raise HTTPException(status_code=500, detail=f"추출 실패: {e}")

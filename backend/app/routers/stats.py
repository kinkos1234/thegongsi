"""공개 커버리지 통계 — 랜딩 페이지 트러스트 시그널용."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Company, Disclosure

router = APIRouter()


@router.get("/coverage")
async def coverage(db: AsyncSession = Depends(get_db)):
    """총 공시 수, 커버되는 기업 수, 최근 7일 이상 공시 수, since, 일평균.

    랜딩 "오늘의 이상 공시" 상단에 트러스트 시그널 + 내러티브로 노출.
    """
    total_disclosures = (
        await db.execute(select(func.count(Disclosure.id)))
    ).scalar_one()
    total_companies = (
        await db.execute(select(func.count(Company.id)))
    ).scalar_one()
    # rcept_dt는 YYYY-MM-DD 형식으로 저장됨(예: "2026-04-15").
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    anomalies_7d = (
        await db.execute(
            select(func.count(Disclosure.id)).where(
                Disclosure.anomaly_severity.in_(["high", "med"]),
                Disclosure.rcept_dt >= cutoff,
            )
        )
    ).scalar_one()
    since = (
        await db.execute(select(func.min(Disclosure.rcept_dt)))
    ).scalar_one()
    since_iso = None
    daily_avg = None
    if since:
        s = str(since)
        # YYYY-MM-DD 또는 YYYYMMDD 양쪽 수용
        try:
            if "-" in s:
                since_dt = datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                since_dt = datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
            since_iso = since_dt.date().isoformat()
            days = max(1, (datetime.now(timezone.utc) - since_dt).days)
            daily_avg = round(int(total_disclosures or 0) / days, 1)
        except ValueError:
            pass

    return {
        "disclosures": int(total_disclosures or 0),
        "companies": int(total_companies or 0),
        "anomalies_7d": int(anomalies_7d or 0),
        "since": since_iso,
        "daily_avg": daily_avg,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ask-suggestions")
async def ask_suggestions(db: AsyncSession = Depends(get_db)):
    """오늘 시점에 던지면 의미 있는 질의 3-5개.

    최근 7일 high+med 공시에서 섹터·키워드를 뽑아 동적 생성.
    백엔드가 맥락 없으면 기본 5개 fallback.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y%m%d")
    res = await db.execute(
        select(Disclosure)
        .where(
            Disclosure.anomaly_severity.in_(["high", "med"]),
            Disclosure.rcept_dt >= cutoff,
        )
        .order_by(Disclosure.rcept_dt.desc())
        .limit(30)
    )
    rows = list(res.scalars().all())

    suggestions: list[str] = []
    seen_sectors: set[str] = set()

    # Company 섹터 lookup
    if rows:
        tickers = list({d.ticker for d in rows})
        crs = await db.execute(select(Company).where(Company.ticker.in_(tickers)))
        sector_map = {c.ticker: c.sector for c in crs.scalars().all() if c.sector}
        for d in rows:
            sec = sector_map.get(d.ticker)
            if sec and sec not in seen_sectors:
                seen_sectors.add(sec)
                suggestions.append(f"{sec} 섹터의 최근 이상 공시")
                if len(suggestions) >= 3:
                    break

    keyword_triggers = {
        "유상증자": "최근 1주일 유상증자 공시한 코스닥 종목",
        "감사의견": "최근 감사의견 '한정'·'의견거절' 공시",
        "최대주주": "최근 최대주주 변경 공시 요약",
        "소송": "진행 중 소송 관련 공시 TOP 5",
        "배당": "이번 주 배당 관련 공시",
    }
    for kw, q in keyword_triggers.items():
        if any(kw in (d.report_nm or "") for d in rows):
            suggestions.append(q)
        if len(suggestions) >= 5:
            break

    # Fallback — 공시 데이터 적거나 쿼리 비어있을 때
    fallback = [
        "HBM 공급망에서 최근 이상 공시가 있는 회사?",
        "최근 1주일 감사의견 변경·한정 공시",
        "SK하이닉스의 주요 공급처와 최근 공시",
        "최대주주 변경이 있었던 코스닥 종목",
        "삼성전자 관련된 자회사·계열사 중 배당 공시",
    ]
    while len(suggestions) < 5:
        fb = fallback.pop(0) if fallback else None
        if not fb:
            break
        if fb not in suggestions:
            suggestions.append(fb)

    return {"suggestions": suggestions[:5]}


@router.get("/pulse")
async def pulse(days: int = 30, db: AsyncSession = Depends(get_db)):
    """최근 N일간 일별 이상 공시(high+med) 카운트 — 히어로 빈 상태 폴백용 리본.

    rcept_dt가 YYYYMMDD 문자열이어서 SUBSTR로 day 파티션. SQLite/Postgres 양쪽 호환.
    """
    from sqlalchemy import literal_column

    days = max(7, min(90, days))
    # rcept_dt는 YYYY-MM-DD 형식
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    res = await db.execute(
        select(
            Disclosure.rcept_dt.label("d"),
            func.count(Disclosure.id).label("n"),
        )
        .where(
            Disclosure.rcept_dt >= cutoff,
            Disclosure.anomaly_severity.in_(["high", "med"]),
        )
        .group_by(Disclosure.rcept_dt)
        .order_by(literal_column("d"))
    )
    rows = [{"date": str(r.d), "count": int(r.n)} for r in res.all()]
    return {"days": days, "series": rows}

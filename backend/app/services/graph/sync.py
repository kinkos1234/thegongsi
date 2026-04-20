"""Postgres Disclosure/Company → Neo4j 동기화.

전략:
- Company row → (:Company {ticker, name_ko, sector, market, corp_code})
- Disclosure row → (:Disclosure {rcept_no, report_nm, rcept_dt, severity, reason})
- edge: (Disclosure)-[:FILED_BY]->(Company)

MERGE를 사용하므로 idempotent. 재실행 시 기존 노드·관계 보존하며 속성만 갱신.

호출 지점:
- scheduler.collect_all → anomaly scan 후 전체 신규 동기화
- backfill_ticker → 특정 ticker 백필 후
- 수동: POST /api/graph/sync (Phase 2)
"""
import logging
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.tables import Company, Disclosure
from app.services.graph.client import run_cypher

logger = logging.getLogger(__name__)


async def sync_company(db: AsyncSession, ticker: str) -> bool:
    """단일 Company를 Neo4j에 upsert. 존재하지 않으면 False."""
    res = await db.execute(select(Company).where(Company.ticker == ticker))
    c = res.scalar_one_or_none()
    if not c:
        return False
    await run_cypher(
        """
        MERGE (co:Company {ticker: $ticker})
        SET co.name_ko = $name_ko,
            co.sector = $sector,
            co.market = $market,
            co.corp_code = $corp_code
        """,
        {
            "ticker": c.ticker,
            "name_ko": c.name_ko or "",
            "sector": c.sector or "",
            "market": c.market or "",
            "corp_code": c.corp_code or "",
        },
    )
    return True


async def sync_disclosures(
    tickers: Iterable[str] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict:
    """Disclosure 테이블을 Neo4j로 sync.

    tickers=None이면 전체, 지정 시 필터.
    limit: 대량 배치 시 상한 (기본 500).
    offset: 페이지네이션용 (기본 0) — `sync_disclosures_all`에서 루프 시 사용.
    """
    async with async_session() as db:
        query = (
            select(Disclosure)
            .order_by(Disclosure.rcept_dt.desc(), Disclosure.rcept_no.desc())
            .offset(offset)
            .limit(limit)
        )
        if tickers:
            tlist = list(tickers)
            query = query.where(Disclosure.ticker.in_(tlist))
        rows = (await db.execute(query)).scalars().all()

        # Company 노드 배치 upsert
        unique_tickers = {d.ticker for d in rows if d.ticker}
        company_params = []
        for t in unique_tickers:
            res2 = await db.execute(select(Company).where(Company.ticker == t))
            c = res2.scalar_one_or_none()
            if c:
                company_params.append({
                    "ticker": c.ticker,
                    "name_ko": c.name_ko or "",
                    "sector": c.sector or "",
                    "market": c.market or "",
                    "corp_code": c.corp_code or "",
                })

    if company_params:
        await run_cypher(
            """
            UNWIND $batch AS row
            MERGE (co:Company {ticker: row.ticker})
            SET co.name_ko = row.name_ko,
                co.sector = row.sector,
                co.market = row.market,
                co.corp_code = row.corp_code
            """,
            {"batch": company_params},
        )
    company_synced = len(company_params)

    # Disclosure 노드 + edge + TimePoint 배치 upsert
    disclosure_params = []
    for d in rows:
        if not d.ticker:
            continue
        y = int(d.rcept_dt[:4]) if d.rcept_dt else 0
        m = int(d.rcept_dt[5:7]) if len(d.rcept_dt) >= 7 else 0
        q = f"{y}Q{(m - 1) // 3 + 1}" if m else ""
        disclosure_params.append({
            "ticker": d.ticker,
            "rcept_no": d.rcept_no,
            "report_nm": d.report_nm,
            "rcept_dt": d.rcept_dt,
            "severity": d.anomaly_severity or "",
            "reason": (d.anomaly_reason or "")[:300],
            "raw_url": d.raw_url or "",
            "year": y,
            "quarter": q,
        })

    # 100건씩 배치 처리 (Neo4j 트랜잭션 크기 제한 고려)
    BATCH_SIZE = 100
    for i in range(0, len(disclosure_params), BATCH_SIZE):
        batch = disclosure_params[i:i + BATCH_SIZE]
        await run_cypher(
            """
            UNWIND $batch AS row
            MERGE (co:Company {ticker: row.ticker})
            MERGE (dis:Disclosure {rcept_no: row.rcept_no})
            SET dis.report_nm = row.report_nm,
                dis.rcept_dt = row.rcept_dt,
                dis.severity = row.severity,
                dis.reason = row.reason,
                dis.raw_url = row.raw_url
            MERGE (dis)-[:FILED_BY]->(co)
            WITH dis, row
            MERGE (tp:TimePoint {date: row.rcept_dt})
            SET tp.year = row.year, tp.quarter = row.quarter
            MERGE (dis)-[:OCCURRED_AT]->(tp)
            """,
            {"batch": batch},
        )
    disclosure_synced = len(disclosure_params)

    logger.info(f"Graph sync: {company_synced} companies, {disclosure_synced} disclosures")
    return {
        "companies": company_synced,
        "disclosures": disclosure_synced,
        "tickers_filter": list(tickers) if tickers else None,
        "rows_fetched": len(rows),
    }


async def sync_all_disclosures(page_size: int = 500, max_pages: int = 200) -> dict:
    """DB 전체 Disclosure를 Neo4j로 일괄 sync — offset 기반 페이지네이션.

    MERGE 기반이라 멱등. 중단 후 재실행 안전.
    """
    total_companies = 0
    total_disclosures = 0
    pages = 0
    for i in range(max_pages):
        res = await sync_disclosures(limit=page_size, offset=i * page_size)
        rows = res.get("rows_fetched", 0)
        if rows == 0:
            break
        total_companies += res.get("companies", 0)
        total_disclosures += res.get("disclosures", 0)
        pages += 1
    return {
        "pages": pages,
        "companies_total": total_companies,
        "disclosures_total": total_disclosures,
        "completed": pages < max_pages,
    }

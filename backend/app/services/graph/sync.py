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


async def sync_disclosures(tickers: Iterable[str] | None = None, limit: int = 500) -> dict:
    """Disclosure 테이블을 Neo4j로 sync.

    tickers=None이면 전체, 지정 시 필터.
    limit: 대량 배치 시 상한 (기본 500).
    """
    async with async_session() as db:
        query = select(Disclosure).order_by(Disclosure.rcept_dt.desc()).limit(limit)
        if tickers:
            tlist = list(tickers)
            query = query.where(Disclosure.ticker.in_(tlist))
        rows = (await db.execute(query)).scalars().all()

        # Company 노드도 먼저 upsert (FILED_BY 대상)
        unique_tickers = {d.ticker for d in rows if d.ticker}
        company_synced = 0
        for t in unique_tickers:
            if await sync_company(db, t):
                company_synced += 1

    # Disclosure 노드 + edge + TimePoint upsert (Bush/Hassabis temporal 1급 시민)
    disclosure_synced = 0
    for d in rows:
        if not d.ticker:
            continue
        # rcept_dt → year / quarter 계산
        y = int(d.rcept_dt[:4]) if d.rcept_dt else 0
        m = int(d.rcept_dt[5:7]) if len(d.rcept_dt) >= 7 else 0
        q = f"{y}Q{(m - 1) // 3 + 1}" if m else ""
        await run_cypher(
            """
            MERGE (co:Company {ticker: $ticker})
            MERGE (dis:Disclosure {rcept_no: $rcept_no})
            SET dis.report_nm = $report_nm,
                dis.rcept_dt = $rcept_dt,
                dis.severity = $severity,
                dis.reason = $reason,
                dis.raw_url = $raw_url
            MERGE (dis)-[:FILED_BY]->(co)
            WITH dis
            MERGE (tp:TimePoint {date: $rcept_dt})
            SET tp.year = $year, tp.quarter = $quarter
            MERGE (dis)-[:OCCURRED_AT]->(tp)
            """,
            {
                "ticker": d.ticker,
                "rcept_no": d.rcept_no,
                "report_nm": d.report_nm,
                "rcept_dt": d.rcept_dt,
                "severity": d.anomaly_severity or "",
                "reason": (d.anomaly_reason or "")[:300],
                "raw_url": d.raw_url or "",
                "year": y,
                "quarter": q,
            },
        )
        disclosure_synced += 1

    logger.info(f"Graph sync: {company_synced} companies, {disclosure_synced} disclosures")
    return {
        "companies": company_synced,
        "disclosures": disclosure_synced,
        "tickers_filter": list(tickers) if tickers else None,
    }

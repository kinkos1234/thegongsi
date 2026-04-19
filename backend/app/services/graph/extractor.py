"""DART 지배구조 보고서 → 엔티티(인물·관계) 추출 + Neo4j upsert.

파이프라인 (P1-7 Week 1):
1. 대상 ticker 선정 → Disclosure 중 '지배구조/임원/주요주주' 키워드 매칭
2. dart-fss로 각 rcept_no 문서 HTML/XML 다운로드 (TODO: 아직 skeleton)
3. Claude tool_use로 {persons: [{name, role, stake_pct}]} 구조화 추출
4. Neo4j MERGE (:Person) + (:Company)-[:LED_BY / HELD_BY]->() 엣지

현재 상태: **LLM tool_use 스켈레톤만 완성**. 실제 문서 fetch는 Phase 2.
테스트용으로 report_nm 문자열만 LLM에 넘겨도 basic 이름 추출 가능.
"""
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.database import async_session
from app.models.tables import (
    Company,
    CorporateOwnership,
    Disclosure,
    Insider,
    MajorShareholder,
)
from app.services.graph.client import run_cypher

logger = logging.getLogger(__name__)


# 지배구조 관련 공시 키워드 (extract 대상)
GOVERNANCE_KEYWORDS = (
    "지배구조보고서",
    "임원·주요주주특정증권등소유상황보고서",
    "최대주주등소유주식변동신고서",
    "주식등의대량보유상황보고서",
    "사외이사선임",
    "대표이사변경",
    "최대주주변경",
)


EXTRACT_TOOL = {
    "name": "extract_governance_entities",
    "description": (
        "공시 정보(특히 지배구조/임원·대주주)에서 인물·법인 주주·역할·지분 엔티티를 추출한다. "
        "추출 불가능하거나 정보 없음이면 빈 배열 반환."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "persons": {
                "type": "array",
                "description": "공시에 등장하는 인물 목록 (회장/대표/사외이사/대주주 등)",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "한국어 성명"},
                        "role": {
                            "type": "string",
                            "description": "역할 (예: 회장, 대표이사, 사외이사, 대주주, 감사)",
                        },
                        "relation": {
                            "type": "string",
                            "enum": ["LEADS", "HOLDS", "UNKNOWN"],
                        },
                        "stake_pct": {
                            "type": "number",
                            "description": "지분율 %. HOLDS일 때만, 없으면 0",
                        },
                        "classification": {
                            "type": "string",
                            "enum": ["exec", "outside", "audit", "unknown"],
                            "description": "임원 분류 — exec(등기/미등기임원), outside(사외이사), audit(감사·감사위원)",
                        },
                        "is_registered": {
                            "type": "boolean",
                            "description": "등기임원 여부. 모르면 null",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0.0~1.0 신뢰도",
                        },
                    },
                    "required": ["name", "role", "relation", "confidence"],
                },
            },
            "corporate_shareholders": {
                "type": "array",
                "description": "법인 주주 목록 — 타 상장사·지주사·해외법인 등",
                "items": {
                    "type": "object",
                    "properties": {
                        "corp_name": {"type": "string", "description": "법인명"},
                        "corp_ticker": {
                            "type": "string",
                            "description": "해당 법인의 한국 상장 ticker (알면). 없으면 빈 문자열",
                        },
                        "stake_pct": {
                            "type": "number",
                            "description": "지분율 %",
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": ["corp_name", "stake_pct", "confidence"],
                },
            },
        },
        "required": ["persons"],
    },
}


EXTRACT_SYSTEM = """한국 DART 공시 메타데이터(제목·날짜·회사명)에서 인물 엔티티를 추출.
모호하거나 추측성은 confidence ≤ 0.5로 표시.
제목만 갖고는 인물 추출 불가인 경우가 대부분 — 빈 배열 반환이 더 안전.
"""


async def extract_from_disclosures(ticker: str, limit: int = 20) -> dict:
    """ticker의 governance 공시들을 묶어 LLM에 넘기고 인물 추출."""
    if not settings.anthropic_api_key:
        return {"status": "no_api_key"}

    async with async_session() as db:
        company_res = await db.execute(select(Company).where(Company.ticker == ticker))
        company = company_res.scalar_one_or_none()
        if not company:
            return {"status": "company_not_found"}

        disc_res = await db.execute(
            select(Disclosure)
            .where(Disclosure.ticker == ticker)
            .order_by(Disclosure.rcept_dt.desc())
            .limit(200)
        )
        all_disc = disc_res.scalars().all()

    # governance 키워드 매칭만 필터
    gov = [d for d in all_disc if any(k in d.report_nm for k in GOVERNANCE_KEYWORDS)][:limit]
    if not gov:
        return {"status": "no_governance_disclosures", "ticker": ticker}

    prompt = f"회사: {company.name_ko} ({ticker})\n\n공시 목록:\n"
    for d in gov:
        prompt += f"- {d.rcept_dt} {d.report_nm}\n"

    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_governance_entities"},
    )

    persons: list[dict[str, Any]] = []
    corporates: list[dict[str, Any]] = []
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "extract_governance_entities":
            persons = list(block.input.get("persons", []))
            corporates = list(block.input.get("corporate_shareholders", []))
            break

    # confidence >= 0.5만 upsert
    accepted_persons = [p for p in persons if p.get("confidence", 0) >= 0.5]
    accepted_corps = [c for c in corporates if c.get("confidence", 0) >= 0.5]
    as_of = datetime.utcnow().strftime("%Y-%m-%d")

    # Neo4j 동기화 (Person/Company 관계)
    for p in accepted_persons:
        person_id = f"p-{p['name'].strip().replace(' ', '-')}"
        await run_cypher(
            "MERGE (p:Person {id: $pid}) SET p.name_ko=$name, p.role=$role",
            {"pid": person_id, "name": p["name"], "role": p["role"]},
        )
        rel = p.get("relation", "UNKNOWN")
        if rel == "LEADS":
            await run_cypher(
                "MATCH (p:Person {id: $pid}) "
                "MATCH (c:Company {ticker: $t}) "
                "MERGE (p)-[r:LEADS]->(c) SET r.role=$role, r.source='dart-extractor'",
                {"pid": person_id, "t": ticker, "role": p["role"]},
            )
        elif rel == "HOLDS":
            await run_cypher(
                "MATCH (p:Person {id: $pid}) "
                "MATCH (c:Company {ticker: $t}) "
                "MERGE (p)-[r:HOLDS]->(c) "
                "SET r.pct=$pct, r.source='dart-extractor'",
                {"pid": person_id, "t": ticker, "pct": p.get("stake_pct", 0)},
            )

    # Company → Company 법인 지분 관계 (Neo4j + SQL 양방향)
    for cshare in accepted_corps:
        corp_ticker = (cshare.get("corp_ticker") or "").strip()
        if corp_ticker:
            await run_cypher(
                "MATCH (parent:Company {ticker: $parent}) "
                "MATCH (child:Company {ticker: $child}) "
                "MERGE (parent)-[r:HOLDS_SHARES]->(child) "
                "SET r.pct=$pct, r.as_of=$as_of, r.source='dart-extractor'",
                {
                    "parent": corp_ticker,
                    "child": ticker,
                    "pct": cshare.get("stake_pct", 0),
                    "as_of": as_of,
                },
            )

    # SQL 스냅샷 적립 — idempotent upsert
    async with async_session() as db:
        for p in accepted_persons:
            rel = p.get("relation", "UNKNOWN")
            if rel == "HOLDS":
                await _upsert_shareholder(
                    db,
                    ticker=ticker,
                    holder_name=p["name"],
                    holder_type="person",
                    stake_pct=p.get("stake_pct"),
                    as_of=as_of,
                )
            elif rel == "LEADS":
                await _upsert_insider(
                    db,
                    ticker=ticker,
                    person_name=p["name"],
                    role=p["role"],
                    classification=p.get("classification"),
                    is_registered=p.get("is_registered"),
                    as_of=as_of,
                )
        for c in accepted_corps:
            corp_ticker = (c.get("corp_ticker") or "").strip() or None
            await _upsert_shareholder(
                db,
                ticker=ticker,
                holder_name=c["corp_name"],
                holder_type="corp",
                stake_pct=c.get("stake_pct"),
                holder_ticker=corp_ticker,
                as_of=as_of,
            )
            if corp_ticker:
                await _upsert_corp_ownership(
                    db,
                    parent_ticker=corp_ticker,
                    child_ticker=ticker,
                    parent_name=c["corp_name"],
                    child_name=company.name_ko,
                    stake_pct=c.get("stake_pct"),
                    as_of=as_of,
                )
        await db.commit()

    return {
        "status": "ok",
        "ticker": ticker,
        "candidates_persons": len(persons),
        "accepted_persons": len(accepted_persons),
        "candidates_corps": len(corporates),
        "accepted_corps": len(accepted_corps),
    }


# DB 방언 중립 upsert — Postgres(pg_insert) / SQLite(sqlite_insert) 모두 on_conflict 지원
def _dialect_insert(db):
    name = db.bind.dialect.name if db.bind else db.get_bind().dialect.name
    return pg_insert if name == "postgresql" else sqlite_insert


async def _upsert_shareholder(
    db,
    *,
    ticker: str,
    holder_name: str,
    holder_type: str,
    as_of: str,
    stake_pct: float | None = None,
    shares: int | None = None,
    holder_ticker: str | None = None,
) -> None:
    ins = _dialect_insert(db)(MajorShareholder).values(
        ticker=ticker,
        holder_name=holder_name,
        holder_type=holder_type,
        stake_pct=stake_pct,
        shares=shares,
        holder_ticker=holder_ticker,
        as_of=as_of,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["ticker", "holder_name", "as_of"],
        set_={
            "holder_type": ins.excluded.holder_type,
            "stake_pct": ins.excluded.stake_pct,
            "shares": ins.excluded.shares,
            "holder_ticker": ins.excluded.holder_ticker,
        },
    )
    await db.execute(stmt)


async def _upsert_insider(
    db,
    *,
    ticker: str,
    person_name: str,
    role: str,
    as_of: str,
    classification: str | None = None,
    is_registered: bool | None = None,
    own_shares: int | None = None,
) -> None:
    ins = _dialect_insert(db)(Insider).values(
        ticker=ticker,
        person_name=person_name,
        role=role,
        classification=classification,
        is_registered=is_registered,
        own_shares=own_shares,
        as_of=as_of,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["ticker", "person_name", "role", "as_of"],
        set_={
            "classification": ins.excluded.classification,
            "is_registered": ins.excluded.is_registered,
            "own_shares": ins.excluded.own_shares,
        },
    )
    await db.execute(stmt)


async def _upsert_corp_ownership(
    db,
    *,
    parent_ticker: str,
    child_ticker: str,
    as_of: str,
    parent_name: str | None = None,
    child_name: str | None = None,
    stake_pct: float | None = None,
) -> None:
    ins = _dialect_insert(db)(CorporateOwnership).values(
        parent_ticker=parent_ticker,
        child_ticker=child_ticker,
        parent_name=parent_name,
        child_name=child_name,
        stake_pct=stake_pct,
        as_of=as_of,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["parent_ticker", "child_ticker", "as_of"],
        set_={
            "parent_name": ins.excluded.parent_name,
            "child_name": ins.excluded.child_name,
            "stake_pct": ins.excluded.stake_pct,
        },
    )
    await db.execute(stmt)

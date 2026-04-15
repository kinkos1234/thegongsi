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
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.tables import Company, Disclosure
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
        "공시 정보(특히 지배구조/임원·대주주)에서 인물·역할·지분 엔티티를 추출한다. "
        "추출 불가능하거나 정보 없음이면 persons=[] 빈 배열 반환."
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
                            "description": "역할 (예: 회장, 대표이사, 사외이사, 대주주)",
                        },
                        "relation": {
                            "type": "string",
                            "enum": ["LEADS", "HOLDS", "UNKNOWN"],
                            "description": "LEADS=경영 이끎, HOLDS=주식 보유, UNKNOWN=불명",
                        },
                        "stake_pct": {
                            "type": "number",
                            "description": "지분율 %. HOLDS일 때만, 없으면 0",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0.0~1.0 신뢰도",
                        },
                    },
                    "required": ["name", "role", "relation", "confidence"],
                },
            }
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
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "extract_governance_entities":
            persons = list(block.input.get("persons", []))
            break

    # confidence >= 0.5만 upsert
    accepted = [p for p in persons if p.get("confidence", 0) >= 0.5]

    for p in accepted:
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

    return {
        "status": "ok",
        "ticker": ticker,
        "candidates": len(persons),
        "accepted": len(accepted),
        "persons": accepted,
    }

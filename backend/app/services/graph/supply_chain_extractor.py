"""공시/뉴스 본문에서 공급·고객 관계를 LLM 으로 추출해 Neo4j SUPPLIES 엣지로 upsert.

seed_supply_chains.yaml 은 "널리 알려진" 관계만 hardcode 한다면, 이 추출기는
DART 공시 본문 (단일판매·공급계약체결 / 사업보고서 고객사 언급 / 지배구조 보고서
등) 을 스캔해 A-B 공급 관계를 자동 발견한다.

전략:
  1. 최근 N일 공시 중 공급 관계 단서가 있는 filings 필터 (키워드: "공급계약",
     "주요고객", "주요 고객사", "매출의 N% 이상" 등)
  2. 각 filing 본문에서 LLM 에게 "{supplier_company}가 공급하는 고객사 목록" 과
     "이 회사의 주요 매출처" 를 JSON 으로 추출
  3. Postgres companies 테이블에서 회사명→ticker 매핑
  4. 매칭된 pair 만 Neo4j SUPPLIES edge upsert (source='extracted', confidence,
     evidence_rcept_no)

보수성 원칙:
  - confidence < 0.6 는 버림
  - ticker 매칭 실패 회사명은 버림 (사람 이름·지명 오인 방지)
  - 같은 (sup, cust) 가 seed 에 이미 있으면 source 덮어쓰지 않음
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


EXTRACT_PROMPT = """너는 한국 상장사 공시·뉴스 본문에서 **공급/고객 관계**만 추출하는 분석가다.

다음 본문에서 "A회사가 B회사에 제품/서비스를 공급한다" 관계를 찾아 JSON 배열로만 답하라. 추론·추측은 금지. 본문에 명시적으로 나온 관계만.

JSON 스키마 (배열, 각 원소):
{
  "supplier": "공급사 회사명 (한국어 정식명)",
  "customer": "고객사 회사명 (한국어 정식명)",
  "role": "equipment|material|component|service|foundry|ip|unknown",
  "evidence": "본문에서 발췌한 1-2문장 (200자 이내)",
  "confidence": 0.0~1.0
}

규칙:
- 본문에 한 번이라도 명시 안 된 관계는 제외.
- "계열사/자회사/지분 관계" 는 공급 관계 아님 → 제외.
- supplier 가 해당 공시의 **주체(신고자)** 와 동일하면 customer 는 본문에 언급된 고객사.
- 불확실하면 confidence 를 0.5 이하로.
- 관계가 0건이면 빈 배열 [].

출력은 ```json 블록 없이 pure JSON 배열만.
"""


def _match_ticker_by_name(name: str, name_to_ticker: dict[str, str]) -> str | None:
    """회사명 정규화 후 정확/부분 매칭. name_to_ticker 는 소문자·공백제거 기준."""
    if not name:
        return None
    norm = re.sub(r"\s+", "", name.lower())
    # 1. 정확 매칭
    if norm in name_to_ticker:
        return name_to_ticker[norm]
    # 2. 약어 매칭: "LG에너지솔루션" ⊇ "LG에너지" 가 있을 때, 본문의 "LG에너지솔루션" 과
    #    DB의 "LG에너지솔루션" 이 정확 매칭되어야 함. 부분 매칭은 오탐 위험 커서 skip.
    # 3. 접미사 제거 매칭: "한미반도체(주)" → "한미반도체"
    stripped = norm.rstrip(")").rstrip("(주").rstrip("㈜").strip()
    if stripped != norm and stripped in name_to_ticker:
        return name_to_ticker[stripped]
    return None


async def _load_company_name_map() -> dict[str, str]:
    """Postgres companies → {normalized_name: ticker}. 동명이인은 첫 ticker만."""
    from app.database import async_session
    from app.models.market import Company
    from sqlalchemy import select

    out: dict[str, str] = {}
    async with async_session() as db:
        r = await db.execute(select(Company.ticker, Company.name_ko))
        for ticker, name in r.all():
            if not name:
                continue
            key = re.sub(r"\s+", "", name.lower())
            out.setdefault(key, ticker)
    logger.info("loaded %d company names for matching", len(out))
    return out


async def _call_claude(prompt_body: str) -> list[dict[str, Any]]:
    """Anthropic SDK 로 Claude 호출. ANTHROPIC_API_KEY 필수."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY missing — extractor skipped")
        return []
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("anthropic SDK not installed")
        return []
    client = AsyncAnthropic(api_key=api_key)
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=EXTRACT_PROMPT,
            messages=[{"role": "user", "content": prompt_body[:8000]}],
            timeout=30,
        )
        text = resp.content[0].text if resp.content else "[]"
        # JSON 블록만 추출 (모델이 markdown 감쌀 경우 대비)
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        return json.loads(m.group())
    except Exception as e:
        logger.warning("claude extract failed: %s", e)
        return []


async def extract_supply_chains(
    days_back: int = 14,
    max_filings: int = 30,
    min_confidence: float = 0.6,
) -> dict[str, Any]:
    """최근 N일 DART 공시 중 공급관계 단서 있는 filings를 대상으로 LLM 추출 →
    SUPPLIES 엣지 upsert. 반환값: {'processed','extracted','upserted','skipped'}."""
    from datetime import date, timedelta
    from sqlalchemy import select
    from app.database import async_session
    from app.models.tables import Disclosure
    from app.services.graph.client import session as graph_session

    end = date.today()
    start = end - timedelta(days=days_back)

    # 공급 관계 단서 키워드 — 신뢰할 수 있는 signals
    SIGNALS = ["단일판매ㆍ공급계약체결", "단일판매·공급계약체결", "주요고객", "주요 매출처",
               "공급계약", "공급 계약"]

    async with async_session() as db:
        q = (
            select(Disclosure)
            .where(Disclosure.filed_at >= start)
            .where(Disclosure.filed_at <= end)
            .order_by(Disclosure.filed_at.desc())
            .limit(max_filings * 3)  # 필터 후 추릴 여유
        )
        candidates = (await db.execute(q)).scalars().all()

    targets = [d for d in candidates if any(sig in (d.title or "") for sig in SIGNALS)][:max_filings]
    logger.info("extract_supply_chains: %d candidates → %d targets", len(candidates), len(targets))

    name_map = await _load_company_name_map()

    upserted = 0
    extracted_total = 0
    skipped = 0

    async with graph_session(read_only=False) as s:
        for d in targets:
            # 본문이 없거나 너무 짧으면 제목만 사용
            body = (d.title or "") + "\n\n" + (d.summary or d.raw_text or "")
            results = await _call_claude(body)
            extracted_total += len(results)
            for r in results:
                try:
                    sup_name = r.get("supplier", "")
                    cust_name = r.get("customer", "")
                    conf = float(r.get("confidence", 0))
                    role = r.get("role", "unknown")
                    evidence = (r.get("evidence") or "")[:500]
                except Exception:
                    skipped += 1
                    continue
                if conf < min_confidence:
                    skipped += 1
                    continue
                sup_t = _match_ticker_by_name(sup_name, name_map)
                cust_t = _match_ticker_by_name(cust_name, name_map)
                if not sup_t or not cust_t or sup_t == cust_t:
                    skipped += 1
                    continue
                # seed 에 이미 있는 엣지는 source 보존 (덮어쓰기 금지)
                await s.run(
                    """
                    MERGE (sup:Company {ticker: $sup_t})
                      ON CREATE SET sup.name_ko = $sup_n
                    MERGE (cust:Company {ticker: $cust_t})
                      ON CREATE SET cust.name_ko = $cust_n
                    MERGE (sup)-[r:SUPPLIES]->(cust)
                      ON CREATE SET r.role = $role,
                                    r.source = 'extracted',
                                    r.confidence = $conf,
                                    r.evidence_rcept_no = $rcept,
                                    r.evidence = $evidence,
                                    r.created_at = datetime()
                      ON MATCH SET  r.last_seen_at = datetime(),
                                    r.confidence = CASE WHEN r.source = 'seed_supply_chains.yaml'
                                                        THEN r.confidence
                                                        ELSE $conf END
                    """,
                    sup_t=sup_t, sup_n=sup_name,
                    cust_t=cust_t, cust_n=cust_name,
                    role=role, conf=conf, rcept=d.rcept_no or "",
                    evidence=evidence,
                )
                upserted += 1

    logger.info(
        "extract_supply_chains: processed=%d extracted=%d upserted=%d skipped=%d",
        len(targets), extracted_total, upserted, skipped,
    )
    return {
        "processed": len(targets),
        "extracted": extracted_total,
        "upserted": upserted,
        "skipped": skipped,
    }

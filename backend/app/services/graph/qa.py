"""GraphRAG + Postgres 하이브리드 Q&A (Claude multi-tool).

플로우:
1. 질문 → Claude가 도구 중 하나 선택:
   - run_cypher  : 관계형 질문 (공급망/경영진/경쟁사)
   - search_disclosures : 키워드 기반 공시 검색
2. 도구 실행 → 결과 수집
3. 결과 → 한국어 답변 합성 (Claude Haiku)

임베딩(pgvector) 없음 — 400 disclosures 규모에선 Claude tool + Postgres
ILIKE가 단순+정확. 10,000+ corpora 때 Voyage/SBERT 재평가 (PRD/06 참고).
"""
import logging
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.tables import Disclosure
from app.services.graph.client import run_cypher

logger = logging.getLogger(__name__)


QA_SYSTEM = """너는 한국 주식 리서치 애널리스트다. 사용자의 자연어 질문에 답하기 위해 필요한 도구를 골라 호출하고, 결과를 한국어로 종합한다.

사용 가능 도구:
1) run_cypher — Neo4j 그래프 질의. 관계형 질문(공급망·경쟁사·인물·지분)에 적합.
2) search_disclosures — Postgres 공시 제목 키워드 검색. 구체적 이슈(유상증자·합병·감사거절 등)에 적합.

여러 도구를 순차 호출해도 좋다. **같은 도구에 같은 args로 2회 이상 호출하지 말 것**.

**중요 — 과도한 재시도 금지:**
- 잘 정의된(focused) 쿼리가 0행 반환 = "데이터 없음"이 정답. 곧바로 최종 답변.
- broadening(조건 완화), alternative keyword, different severity 등 3회 이상 시도 금지.
- 3번의 유의미한 hop 안에서 답이 안 나오면 '현재 데이터로는 확인 불가'로 답변.

복합 질문 전략:
- '공급망 + 공시 심각도' 같은 cross 질문 → 먼저 run_cypher로 공급망 ticker 얻고, **단일** search_disclosures에 그 ticker 중 핵심 하나만 필터 (또는 Cypher IN 절). 모든 ticker를 개별 호출하지 말 것.
- 시간·집계(top N, count) → run_cypher COUNT + ORDER BY DESC (1 hop)
- 결과 일부만 반환돼도 OK. LIMIT 명시하고 답변에 '일부' 표기

답변 형식: 한국어, 간결한 표 또는 2~4문장, 경어.
결과가 비면 '해당 조건의 데이터가 없습니다.' 로 시작하고 즉시 종료.

절대 금지:
- 투자자문·매수추천 문구
- '⚠️ 투자 추천이 아닙니다' 같은 disclaimer/경고 (UI에서 별도 표시)
- blockquote 경고 블록"""


# Neo4j 스키마 (Cypher 생성 시 참고)
NEO4J_SCHEMA_HINT = """Neo4j 스키마:
- (:Company {corp_code, ticker, name_ko, sector, market})
- (:Person {id, name_ko, role})
- (:Disclosure {rcept_no, report_nm, rcept_dt, severity, reason})
- (:TimePoint {date, year, quarter})
- (Company)-[:COMPETES_WITH]->(Company)
- (Company)-[:SUPPLIES]->(Company)
- (Company)-[:OWNS {pct}]->(Company)
- (Person)-[:LEADS]->(Company)
- (Person)-[:HOLDS {pct}]->(Company)
- (Disclosure)-[:FILED_BY]->(Company)
- (Disclosure)-[:OCCURRED_AT]->(TimePoint)

severity: 'high','med','low','uncertain'. rcept_dt: 'YYYY-MM-DD' 문자열(date() 함수 금지). LIMIT 25 이하."""


TOOLS = [
    {
        "name": "run_cypher",
        "description": (
            "Neo4j 그래프에 READ-ONLY Cypher 쿼리 실행. 관계형·구조적 질문에 사용. "
            f"{NEO4J_SCHEMA_HINT}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cypher": {"type": "string", "description": "MATCH ... RETURN ... Cypher"},
            },
            "required": ["cypher"],
        },
    },
    {
        "name": "search_disclosures",
        "description": (
            "Postgres 공시 테이블을 키워드 ILIKE로 검색. "
            "구체적 이슈(유상증자·합병·감사·최대주주변경 등) 찾을 때 사용. "
            "keywords는 OR 매칭: 하나라도 포함되면 hit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "부분 일치 키워드 (한국어)",
                },
                "ticker": {"type": "string", "description": "6자리 종목코드 필터 (선택)"},
                "severity": {
                    "type": "string",
                    "enum": ["high", "med", "low", "uncertain"],
                    "description": "severity 필터 (선택)",
                },
                "since": {"type": "string", "description": "'YYYY-MM-DD' 이후만"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["keywords"],
        },
    },
]


FORBIDDEN = ["CREATE", "MERGE", "DELETE", "SET ", "REMOVE", "DROP", "CALL "]


def is_safe(cypher: str) -> bool:
    upper = cypher.upper()
    return not any(kw in upper for kw in FORBIDDEN)


async def _tool_run_cypher(args: dict) -> Any:
    cypher = args.get("cypher", "").strip()
    if cypher.startswith("```"):
        cypher = cypher.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
        if cypher.startswith("cypher"):
            cypher = cypher[len("cypher"):].strip()
    if not is_safe(cypher):
        return {"error": "Unsafe Cypher rejected"}
    rows = await run_cypher(cypher, read_only=True)
    return {"cypher": cypher, "rows": rows[:25]}


async def _tool_search_disclosures(args: dict) -> Any:
    keywords = args.get("keywords", [])
    if not keywords:
        return {"error": "keywords required"}
    ticker = args.get("ticker")
    severity = args.get("severity")
    since = args.get("since")
    limit = min(int(args.get("limit", 20)), 100)

    async with async_session() as db:
        q = select(Disclosure).order_by(Disclosure.rcept_dt.desc())
        # OR 조건 (ILIKE fallback on LIKE for SQLite)
        from sqlalchemy import or_, func
        clauses = [func.lower(Disclosure.report_nm).like(f"%{k.lower()}%") for k in keywords]
        q = q.where(or_(*clauses))
        if ticker:
            q = q.where(Disclosure.ticker == ticker)
        if severity:
            q = q.where(Disclosure.anomaly_severity == severity)
        if since:
            q = q.where(Disclosure.rcept_dt >= since)
        q = q.limit(limit)
        rows = (await db.execute(q)).scalars().all()
    return {
        "count": len(rows),
        "rows": [
            {
                "rcept_no": d.rcept_no,
                "ticker": d.ticker,
                "title": d.report_nm,
                "date": d.rcept_dt,
                "severity": d.anomaly_severity,
            }
            for d in rows
        ],
    }


TOOL_DISPATCH = {
    "run_cypher": _tool_run_cypher,
    "search_disclosures": _tool_search_disclosures,
}


async def ask(question: str, user=None, max_hops: int = 6) -> dict:
    """Multi-tool Q&A. Claude가 도구 선택 → 결과 → 최종 합성까지 agentic loop.

    BYOK: user 인자 주어지면 그 사용자의 byok_anthropic_key 사용 (없으면 서버 키).
    max_hops=6: 다중 도구 조합이 필요한 복합 질문(graph+disclosure filter 등) 대응.
    """
    from app.services.llm_client import get_anthropic_client
    client, _owner = get_anthropic_client(user)

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    tool_calls_made: list[dict[str, Any]] = []
    max_total_calls = 8  # 하드 상한 — Claude가 loop 빠지는 것 방지

    for _hop in range(max_hops):
        if len(tool_calls_made) >= max_total_calls:
            # 마지막 한 번만 텍스트 답변 요청
            messages.append({
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": "더 이상 도구 호출 없이 지금까지의 결과로 최종 답변을 주세요.",
                }],
            })
            final = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                system=QA_SYSTEM,
                messages=messages,
            )
            answer_text = "".join(
                getattr(b, "text", "") for b in final.content if getattr(b, "type", None) == "text"
            ).strip()
            return {
                "question": question,
                "tools_used": tool_calls_made,
                "answer": answer_text or "현재 데이터로는 확인 불가.",
            }
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=QA_SYSTEM,
            messages=messages,
            tools=TOOLS,
        )

        # 도구 호출 없고 최종 답변이면 종료
        if msg.stop_reason != "tool_use":
            answer_text = "".join(
                getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text"
            ).strip()
            return {
                "question": question,
                "tools_used": tool_calls_made,
                "answer": answer_text or None,
            }

        # assistant message + tool_use 블록 보존
        messages.append({"role": "assistant", "content": msg.content})

        tool_results = []
        for block in msg.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            args = block.input or {}
            handler = TOOL_DISPATCH.get(name)
            if not handler:
                result = {"error": f"unknown tool {name}"}
            else:
                try:
                    result = await handler(args)
                except Exception as e:
                    logger.exception(f"tool {name} failed")
                    result = {"error": str(e)}
            tool_calls_made.append({"name": name, "args": args, "result_summary": _summarize(result)})
            import json as _json
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": _json.dumps(result, ensure_ascii=False)[:6000],
            })

        messages.append({"role": "user", "content": tool_results})

    # max_hops 초과
    return {
        "question": question,
        "tools_used": tool_calls_made,
        "answer": "도구 호출이 허용 횟수를 초과했습니다.",
    }


def _summarize(result: Any) -> dict:
    if not isinstance(result, dict):
        return {"type": type(result).__name__}
    if "rows" in result:
        return {"row_count": len(result["rows"])}
    if "error" in result:
        return {"error": result["error"][:100]}
    return {"keys": list(result.keys())}

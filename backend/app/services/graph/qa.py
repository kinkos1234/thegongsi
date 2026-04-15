"""GraphRAG 자연어 Q&A.

플로우:
1. 질문 → Cypher 생성 (Claude few-shot)
2. Cypher 실행 (read-only 가드)
3. pgvector 유사도 검색 (공시/뉴스 embedding)
4. 결과 + 인용 → 최종 한국어 답변 (Claude)

현재는 skeleton — Cypher 생성 프롬프트 + 가드만.
"""
import logging

from app.config import settings
from app.services.graph.client import run_cypher

logger = logging.getLogger(__name__)

CYPHER_SYSTEM = """너는 Neo4j Cypher 전문가다. 사용자의 한국어 질문을 Cypher로 변환한다.

스키마:
- (:Company {corp_code, ticker, name_ko, sector, market})
- (:Person {id, name_ko, role})
- (:Product {id, name, category})
- (Company)-[:COMPETES_WITH {strength}]->(Company)
- (Company)-[:SUPPLIES {category, since}]->(Company)
- (Company)-[:OWNS {pct}]->(Company)
- (Person)-[:LEADS {role, since}]->(Company)
- (Person)-[:HOLDS {pct}]->(Company)

규칙:
- READ ONLY. CREATE/MERGE/DELETE/SET/REMOVE 금지.
- 결과는 LIMIT 25 이하.
- 변수명은 영문 소문자.
- Cypher만 반환, 설명·주석 금지.
"""

FORBIDDEN = ["CREATE", "MERGE", "DELETE", "SET ", "REMOVE", "DROP", "CALL "]


def is_safe(cypher: str) -> bool:
    upper = cypher.upper()
    return not any(kw in upper for kw in FORBIDDEN)


async def generate_cypher(question: str) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required for GraphRAG")
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=CYPHER_SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    cypher = msg.content[0].text.strip()
    # 코드펜스 제거
    if cypher.startswith("```"):
        cypher = cypher.strip("`").split("\n", 1)[-1].rsplit("\n", 1)[0]
        if cypher.startswith("cypher"):
            cypher = cypher[len("cypher"):].strip()
    if not is_safe(cypher):
        raise ValueError(f"Unsafe Cypher rejected: {cypher[:100]}")
    return cypher


ANSWER_SYSTEM = """너는 한국 주식 리서치 애널리스트다. 그래프 DB 조회 결과(rows)를 바탕으로 사용자 질문에 한국어로 답변한다.

규칙:
- 결과만 근거로 답. 없는 정보 추측 금지.
- 회사명·인물명 등 고유명사는 rows에 있는 표기 그대로.
- 2~4문장, 경어. 숫자는 mono 스타일 유지(백틱 사용).
- 결과가 비면 "해당 조건의 데이터가 그래프에 없습니다." 로 시작.
- 투자자문·추천 금지.
"""


async def ask(question: str) -> dict:
    """Q&A 2-hop: Cypher 생성 → 실행 → 한국어 답변 합성."""
    cypher = await generate_cypher(question)
    rows = await run_cypher(cypher)

    # 2-hop: 한국어 답변 합성
    answer = None
    if settings.anthropic_api_key:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            import json as _json
            msg = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                system=ANSWER_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"질문: {question}\n\nrows:\n{_json.dumps(rows[:25], ensure_ascii=False, indent=2)}",
                }],
            )
            answer = msg.content[0].text.strip()
        except Exception as e:
            logger.warning(f"answer synth failed: {e}")

    return {"question": question, "cypher": cypher, "rows": rows[:25], "answer": answer}

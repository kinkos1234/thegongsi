"""Neo4j 시드 데이터.

HBM 공급망 미니 그래프. DART 키 없이도 GraphRAG Q&A 데모 가능.

사용법:
    python scripts/seed_graph.py

예시 질문:
- "삼성전자 HBM 공급망에 있는 회사들?"
- "SK하이닉스의 경쟁사는?"
- "이재용이 이끄는 회사들?"
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.graph.client import close, run_cypher
from app.services.graph.schema import init_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

COMPANIES = [
    {"corp_code": "00126380", "ticker": "005930", "name_ko": "삼성전자", "sector": "반도체", "market": "KOSPI"},
    {"corp_code": "00164779", "ticker": "000660", "name_ko": "SK하이닉스", "sector": "반도체", "market": "KOSPI"},
    {"corp_code": "00401731", "ticker": "042700", "name_ko": "한미반도체", "sector": "반도체장비", "market": "KOSPI"},
    {"corp_code": "00258801", "ticker": "009150", "name_ko": "삼성전기", "sector": "전자부품", "market": "KOSPI"},
    {"corp_code": "00108432", "ticker": "097950", "name_ko": "CJ제일제당", "sector": "음식료", "market": "KOSPI"},
    {"corp_code": "00101998", "ticker": "051910", "name_ko": "LG화학", "sector": "화학", "market": "KOSPI"},
]

PERSONS = [
    {"id": "lee-jaeyong", "name_ko": "이재용", "role": "회장"},
    {"id": "choi-taewon", "name_ko": "최태원", "role": "회장"},
]

# (source, rel, target, props)
RELATIONSHIPS = [
    ("005930", "COMPETES_WITH", "000660", {"strength": 0.9}),  # 삼성↔하이닉스 메모리
    ("042700", "SUPPLIES", "000660", {"category": "HBM 본더", "since": "2020"}),
    ("042700", "SUPPLIES", "005930", {"category": "패키징 장비", "since": "2019"}),
    ("009150", "SUPPLIES", "005930", {"category": "MLCC·카메라모듈", "since": "2000"}),
    ("lee-jaeyong", "LEADS", "005930", {"role": "회장", "since": "2022"}),
    ("choi-taewon", "LEADS", "000660", {"role": "회장", "since": "2012"}),
]


async def seed():
    await init_schema()

    for c in COMPANIES:
        await run_cypher(
            "MERGE (c:Company {corp_code: $corp_code}) "
            "SET c.ticker=$ticker, c.name_ko=$name_ko, c.sector=$sector, c.market=$market",
            c,
        )
    logger.info(f"Companies: {len(COMPANIES)} merged")

    for p in PERSONS:
        await run_cypher(
            "MERGE (p:Person {id: $id}) SET p.name_ko=$name_ko, p.role=$role",
            p,
        )
    logger.info(f"Persons: {len(PERSONS)} merged")

    for src, rel, tgt, props in RELATIONSHIPS:
        if rel == "LEADS":
            await run_cypher(
                f"MATCH (p:Person {{id: $src}}), (c:Company {{ticker: $tgt}}) "
                f"MERGE (p)-[r:LEADS]->(c) SET r += $props",
                {"src": src, "tgt": tgt, "props": props},
            )
        else:
            await run_cypher(
                f"MATCH (a:Company {{ticker: $src}}), (b:Company {{ticker: $tgt}}) "
                f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
                {"src": src, "tgt": tgt, "props": props},
            )
    logger.info(f"Relationships: {len(RELATIONSHIPS)} merged")

    await close()


if __name__ == "__main__":
    asyncio.run(seed())

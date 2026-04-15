"""Neo4j 스키마 초기화 (제약조건 + 인덱스).

부팅 1회 또는 마이그레이션으로 호출.
"""
from app.services.graph.client import run_cypher

CONSTRAINTS = [
    "CREATE CONSTRAINT company_corp_code IF NOT EXISTS FOR (c:Company) REQUIRE c.corp_code IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (pr:Product) REQUIRE pr.id IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX company_ticker IF NOT EXISTS FOR (c:Company) ON (c.ticker)",
    "CREATE INDEX company_name_ko IF NOT EXISTS FOR (c:Company) ON (c.name_ko)",
]


async def init_schema():
    for q in CONSTRAINTS + INDEXES:
        await run_cypher(q)

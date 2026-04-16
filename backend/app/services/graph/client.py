"""Neo4j 드라이버 래퍼.

설정: NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD (app.config.settings).
comad-brain(7688)과 별도 인스턴스 사용 권장 (7687).
"""
import logging
from contextlib import asynccontextmanager

from app.config import settings

logger = logging.getLogger(__name__)

_driver = None


def get_driver():
    """지연 초기화 싱글턴. 테스트 시 monkeypatch 가능."""
    global _driver
    if _driver is None:
        from neo4j import AsyncGraphDatabase
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_url,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


@asynccontextmanager
async def session(read_only: bool = False):
    """read_only=True → Neo4j 서버가 쓰기 연산을 reject (Torvalds·LeCun: 키워드 파싱 대신 DB 강제)."""
    from neo4j import READ_ACCESS, WRITE_ACCESS
    driver = get_driver()
    access_mode = READ_ACCESS if read_only else WRITE_ACCESS
    async with driver.session(
        default_access_mode=access_mode,
        database=settings.neo4j_database,
    ) as s:
        yield s


async def run_cypher(query: str, params: dict | None = None, read_only: bool = False) -> list[dict]:
    async with session(read_only=read_only) as s:
        result = await s.run(query, params or {})
        return [dict(record) for record in await result.data()]


async def close():
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None

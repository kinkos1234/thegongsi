"""Neo4j 스키마 초기화 — 제약조건 + 인덱스 생성.

사용법:
    python scripts/init_graph.py

idempotent (IF NOT EXISTS). 반복 실행 안전.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.graph.client import close
from app.services.graph.schema import init_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Neo4j 스키마 초기화 시작…")
    await init_schema()
    logger.info("완료. 제약·인덱스 ready.")
    await close()


if __name__ == "__main__":
    asyncio.run(main())

"""Postgres → Neo4j AuraDB 초기 sync.

사용법:
    # Supabase Postgres + AuraDB 연결정보가 .env에 설정된 상태에서
    python scripts/sync_auradb.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph.sync import sync_disclosures


async def main():
    print("AuraDB로 전체 Disclosure sync 시작...")
    result = await sync_disclosures(limit=10000)
    print(f"완료: {result}")


if __name__ == "__main__":
    asyncio.run(main())

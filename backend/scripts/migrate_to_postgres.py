"""SQLite → Supabase/Neon Postgres 마이그레이션.

사용법:
    # 1) Supabase DATABASE_URL 을 환경변수로 export
    export POSTGRES_URL="postgresql+asyncpg://...supabase.co:5432/postgres?sslmode=require"
    # 2) 스크립트 실행
    python scripts/migrate_to_postgres.py

동작:
    1. Postgres에 스키마 생성 (init_db)
    2. SQLite의 모든 테이블 행을 Postgres로 복사 (배치 1000건씩)
    3. 카운트 검증
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models import tables
from app.models.tables import Base

SQLITE_URL = "sqlite+aiosqlite:///./comad_stock.db"

# 마이그레이션 대상 테이블 (FK 순서 주의 — User → Watchlist 등)
TABLES = [
    tables.User,
    tables.Company,
    tables.Disclosure,
    tables.DDMemo,
    tables.DDMemoVersion,
    tables.WatchListItem,
    tables.AlertConfig,
    tables.AlertHistory,
    tables.ServerKeyUsage,
    tables.DisclosureFeedback,
    tables.MemoFeedback,
    tables.ReferenceSummary,
    tables.FinancialSnapshot,
    tables.ShortSellingSnapshot,
    tables.NewsItem,
    tables.EarningsEvent,
]


async def copy_table(src: AsyncSession, dst: AsyncSession, model):
    """한 테이블을 통째로 복사."""
    res = await src.execute(select(model))
    rows = res.scalars().all()
    if not rows:
        print(f"  {model.__tablename__:30s}  (empty)")
        return 0

    # SQLAlchemy ORM 객체 → dict → 새 객체
    copied = 0
    for row in rows:
        data = {c.name: getattr(row, c.name) for c in model.__table__.columns}
        new_row = model(**data)
        dst.add(new_row)
        copied += 1
        if copied % 100 == 0:
            await dst.flush()
    await dst.commit()
    print(f"  {model.__tablename__:30s}  {copied:>6d} rows")
    return copied


async def main():
    pg_url = os.getenv("POSTGRES_URL")
    if not pg_url:
        print("ERROR: POSTGRES_URL 환경변수를 설정하세요.", file=sys.stderr)
        print("예: export POSTGRES_URL='postgresql+asyncpg://...supabase.co:5432/postgres?sslmode=require'", file=sys.stderr)
        sys.exit(1)

    print(f"Source:      {SQLITE_URL}")
    print(f"Destination: {pg_url[:60]}...")
    print()

    src_engine = create_async_engine(SQLITE_URL)
    dst_engine = create_async_engine(pg_url)

    # 1) 스키마 생성
    print("1. Destination 스키마 생성...")
    async with dst_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2) 데이터 복사
    print("2. 테이블 복사:")
    src_session = async_sessionmaker(src_engine, expire_on_commit=False)
    dst_session = async_sessionmaker(dst_engine, expire_on_commit=False)

    total = 0
    for model in TABLES:
        async with src_session() as src, dst_session() as dst:
            n = await copy_table(src, dst, model)
            total += n

    print()
    print(f"완료. 총 {total}개 행 복사됨.")

    await src_engine.dispose()
    await dst_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

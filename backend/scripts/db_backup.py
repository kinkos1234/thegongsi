"""Postgres DB 핵심 테이블 덤프 → JSONL (Supabase 무료티어 백업 보강).

pg_dump 없이 asyncpg로 주요 테이블만 JSONL 스트림 저장.
S3 업로드는 선택 (AWS_ACCESS_KEY_ID 있으면 boto3, 없으면 로컬만).

사용:
    python scripts/db_backup.py                    # ./backups/YYYYMMDD/*.jsonl
    python scripts/db_backup.py --out /path/to/dir # 출력 디렉토리 지정
"""
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TABLES = [
    "companies",
    "disclosures",
    "dd_memos",
    "dd_memo_versions",
    "news_items",
    "earnings_events",
    "calendar_events",
    "alert_configs",
    "alert_history",
    "disclosure_feedback",
    "memo_feedback",
    "watchlist_items",
    "users",  # 이메일·해시 포함 — 보안 저장 주의
]


def _to_asyncpg_dsn(url: str) -> str:
    for p in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(p):
            return url.replace(p, "postgresql://", 1)
    return url


def _default_converter(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"non-serializable: {type(obj)}")


async def dump_table(conn, table: str, out_path: Path) -> int:
    try:
        rows = await conn.fetch(f"SELECT * FROM {table}")
    except Exception as e:
        logger.warning(f"{table} skip: {e}")
        return 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(dict(r), ensure_ascii=False, default=_default_converter))
            f.write("\n")
    logger.info(f"  {table}: {len(rows)} rows → {out_path.name}")
    return len(rows)


async def main(out_root: Path):
    url = _to_asyncpg_dsn(os.environ.get("DATABASE_URL", ""))
    if not url.startswith("postgres"):
        logger.error("Postgres DATABASE_URL 필요"); sys.exit(1)

    today = date.today().strftime("%Y%m%d")
    out_dir = out_root / today
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"백업 대상: {out_dir}")

    import asyncpg
    conn = await asyncpg.connect(url)
    total = 0
    try:
        meta = {"started_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
        for t in TABLES:
            n = await dump_table(conn, t, out_dir / f"{t}.jsonl")
            meta["tables"][t] = n
            total += n
        meta["total_rows"] = total
        meta["finished_at"] = datetime.now(timezone.utc).isoformat()
        (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    finally:
        await conn.close()
    logger.info(f"완료: {total} rows across {len(TABLES)} tables → {out_dir}")

    # S3 업로드 (옵션)
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("BACKUP_S3_BUCKET"):
        try:
            import boto3
            s3 = boto3.client("s3")
            bucket = os.environ["BACKUP_S3_BUCKET"]
            for p in out_dir.glob("*"):
                key = f"the-gongsi/backups/{today}/{p.name}"
                s3.upload_file(str(p), bucket, key)
            logger.info(f"S3 업로드 완료: s3://{bucket}/the-gongsi/backups/{today}/")
        except Exception as e:
            logger.warning(f"S3 업로드 실패 (로컬 백업은 보존): {e}")


if __name__ == "__main__":
    out = Path("./backups")
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    asyncio.run(main(out))

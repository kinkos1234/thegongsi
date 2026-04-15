"""최초 설치 후 DB 부트스트랩 — 시장 전체 최근 N일 공시 + anomaly + Neo4j sync.

Usage:
    python scripts/bootstrap.py               # default 90일
    python scripts/bootstrap.py --days 30
    python scripts/bootstrap.py --days 180 --seed   # HBM 공급망 시드까지

목적: clone 직후 빈 그래프/DB에 의미있는 샘플 데이터 즉시 주입.
- DART 10k req/day 예산 내: 90일 * 일평균 200건 = 18,000 → routine 필터 후 ~2,000건

소요 시간 기준 (M1/M2 Mac):
- 90일 market-wide fetch: ~30s (DART API)
- 1,500~2,000 anomaly scan (LLM Haiku): 5~8분
- Neo4j sync: ~20s
총 ~8-10분
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bootstrap")

KST = timezone(timedelta(hours=9))


async def bootstrap(days: int, seed: bool):
    from app.database import init_db
    from app.services.collectors.dart import _fetch_filings_sync
    from app.services.collectors.krx import fetch_kospi_quotes
    from app.services.graph.schema import init_schema
    from app.services.graph.sync import sync_disclosures
    from app.services.anomaly.detector import scan_new_disclosures

    # 1. DB/그래프 스키마
    logger.info("1/6 init DB + Neo4j schema")
    await init_db()
    try:
        await init_schema()
    except Exception as e:
        logger.warning(f"Neo4j schema init 실패 (계속 진행): {e}")

    # 2. seed graph (선택)
    if seed:
        logger.info("2/6 seed graph (HBM 공급망 토이)")
        try:
            from app.services.graph.client import run_cypher
            from scripts.seed_graph import COMPANIES, PERSONS, RELATIONSHIPS
            for c in COMPANIES:
                await run_cypher(
                    "MERGE (c:Company {corp_code: $corp_code}) "
                    "SET c.ticker=$ticker, c.name_ko=$name_ko, c.sector=$sector, c.market=$market",
                    c,
                )
            for p in PERSONS:
                await run_cypher(
                    "MERGE (p:Person {id: $id}) SET p.name_ko=$name_ko, p.role=$role",
                    p,
                )
            for src, rel, tgt, props in RELATIONSHIPS:
                if rel == "LEADS":
                    await run_cypher(
                        "MATCH (p:Person {id: $src}) MATCH (c:Company {ticker: $tgt}) "
                        "MERGE (p)-[r:LEADS]->(c) SET r += $props",
                        {"src": src, "tgt": tgt, "props": props},
                    )
                else:
                    await run_cypher(
                        f"MATCH (a:Company {{ticker: $src}}) MATCH (b:Company {{ticker: $tgt}}) "
                        f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
                        {"src": src, "tgt": tgt, "props": props},
                    )
            logger.info(f"seed: {len(COMPANIES)} companies, {len(PERSONS)} persons, {len(RELATIONSHIPS)} edges")
        except Exception as e:
            logger.warning(f"seed_graph 실패 (계속 진행): {e}")

    # 3. Company 테이블 자동 seed (KOSPI 200 + KOSDAQ 150, pykrx + dart-fss)
    logger.info("3/6 seed Company (KOSPI 200 + KOSDAQ 150 via pykrx)")
    try:
        from scripts.seed_market_index import seed as seed_market
        r = await seed_market(kospi=True, kosdaq=True, sector_rep=0)
        logger.info(f"Company seed: {r}")
    except Exception as e:
        logger.warning(f"Company seed 실패 (계속 진행): {e}")

    # 4. DART 시장 전체 N일 백필
    now = datetime.now(KST)
    end_de = now.strftime("%Y%m%d")
    bgn_de = (now - timedelta(days=days)).strftime("%Y%m%d")
    logger.info(f"4/6 DART market fetch {bgn_de}~{end_de} (days={days}, max 2000)")
    loop = asyncio.get_event_loop()
    try:
        rows = await loop.run_in_executor(None, _fetch_filings_sync, bgn_de, end_de, 2000)
        logger.info(f"DART: {len(rows)} non-routine disclosures fetched")
    except Exception as e:
        logger.exception(f"DART fetch failed")
        return {"status": "dart_error", "error": str(e)}

    # Postgres upsert
    from sqlalchemy import select
    from app.database import async_session
    from app.models.tables import Disclosure
    inserted = 0
    async with async_session() as db:
        for row in rows:
            if not row["ticker"]:
                continue
            ex = await db.execute(select(Disclosure).where(Disclosure.rcept_no == row["rcept_no"]))
            if ex.scalar_one_or_none():
                continue
            db.add(Disclosure(**row))
            inserted += 1
        await db.commit()
    logger.info(f"Postgres: {inserted} disclosures inserted")

    # 5. KRX 샘플 시세
    try:
        logger.info("5/6 KRX sample quotes")
        await fetch_kospi_quotes()
    except Exception as e:
        logger.warning(f"KRX fetch 실패 (계속): {e}")

    # 6. Anomaly scan + graph sync
    logger.info("6/6 anomaly scan (LLM Haiku) + Neo4j sync — 수 분 소요")
    try:
        anomaly = await scan_new_disclosures()
        logger.info(f"anomaly: {anomaly}")
    except Exception as e:
        logger.warning(f"anomaly scan 실패: {e}")

    try:
        sync = await sync_disclosures(limit=2000)
        logger.info(f"graph sync: {sync}")
    except Exception as e:
        logger.warning(f"graph sync 실패: {e}")

    logger.info(f"bootstrap 완료. /c/005930 등으로 확인 가능")
    return {"status": "ok", "inserted": inserted}


if __name__ == "__main__":
    days = 90
    seed = False
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    if "--seed" in sys.argv:
        seed = True
    asyncio.run(bootstrap(days=days, seed=seed))

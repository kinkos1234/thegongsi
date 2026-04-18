"""공급망 seed — backend/data/supply_chains.yaml 을 읽어 Neo4j 에 upsert.

(SupplierCompany)-[:SUPPLIES {role, source}]->(CustomerCompany) 엣지 생성.
Neo4j 에 Company 노드 없으면 ticker + name 으로 MERGE.

사용:
    python scripts/seed_supply_chains.py

안전: idempotent. 같은 (supplier, customer) 쌍은 MERGE 로 덮어쓰기.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts._logging_setup import setup_script_logging
setup_script_logging()
logger = logging.getLogger(__name__)

import yaml

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "supply_chains.yaml"


async def main():
    from app.services.graph.client import session

    with open(SEED_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    chains = data.get("chains", [])
    total_edges = 0
    total_companies = 0

    async with session(read_only=False) as s:
        for chain in chains:
            cust_ticker = chain.get("customer_ticker") or ""
            cust_name = chain.get("customer") or cust_ticker
            category = chain.get("category") or ""
            suppliers = chain.get("suppliers") or []

            if not cust_ticker:
                logger.warning("skip chain without customer_ticker: %s", cust_name)
                continue

            # customer Company MERGE (ticker 기준)
            await s.run(
                "MERGE (c:Company {ticker: $t}) ON CREATE SET c.name_ko = $n",
                t=cust_ticker, n=cust_name,
            )
            total_companies += 1

            for sup in suppliers:
                sup_ticker = sup.get("ticker") or ""
                sup_name = sup.get("name") or sup_ticker
                role = sup.get("role") or "unknown"
                if not sup_ticker:
                    continue
                # supplier Company MERGE + SUPPLIES edge MERGE
                await s.run(
                    """
                    MERGE (sup:Company {ticker: $sup_t})
                      ON CREATE SET sup.name_ko = $sup_n
                    MERGE (cust:Company {ticker: $cust_t})
                    MERGE (sup)-[r:SUPPLIES]->(cust)
                      ON CREATE SET r.role = $role,
                                    r.category = $cat,
                                    r.source = 'seed_supply_chains.yaml',
                                    r.created_at = datetime()
                      ON MATCH SET  r.role = $role,
                                    r.category = $cat,
                                    r.source = 'seed_supply_chains.yaml',
                                    r.updated_at = datetime()
                    """,
                    sup_t=sup_ticker, sup_n=sup_name,
                    cust_t=cust_ticker, role=role, cat=category,
                )
                total_edges += 1
                total_companies += 1

        # 요약
        r = await s.run("MATCH ()-[r:SUPPLIES]->() RETURN count(r) AS c")
        count_rec = await r.single()
        final_edges = count_rec["c"] if count_rec else 0

    logger.info("seeded %d supplier edges; total SUPPLIES in graph: %d", total_edges, final_edges)
    logger.info("touched %d company nodes (merged)", total_companies)
    return {"edges_seeded": total_edges, "total_supplies_in_graph": final_edges}


if __name__ == "__main__":
    asyncio.run(main())

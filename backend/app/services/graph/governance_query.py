"""지배구조 조회 — SQL 스냅샷 + Neo4j 관계 질의 하이브리드.

전략:
- **빠른 대시보드 조회**: SQL `MajorShareholder`/`Insider`/`CorporateOwnership`에서 최근 as_of 스냅샷
- **관계·경로**: Neo4j에서 순환출자 고리(cycle detection) 및 모자회사 체인 탐색

Neo4j 미설정 시에도 SQL 데이터만으로 동작.
"""
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import (
    Company,
    CorporateOwnership,
    Insider,
    MajorShareholder,
)


def _dedupe_linked(rows: list[dict]) -> list[dict]:
    """Collapse duplicate legal-entity links before they reach the UI.

    Governance extraction may resolve the same Korean company name to an old or
    alternate ticker. For investor-facing views, a duplicated name is more
    damaging than a conservative omission, so keep the strongest stake per name.
    """
    by_key: dict[str, dict] = {}
    for row in rows:
        name = str(row.get("name") or "").strip().lower()
        ticker = str(row.get("ticker") or "").strip()
        key = name or ticker
        if not key:
            continue
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = row
            continue
        prev_stake = prev.get("stake_pct")
        row_stake = row.get("stake_pct")
        if row_stake is not None and (prev_stake is None or row_stake > prev_stake):
            by_key[key] = row
    return sorted(
        by_key.values(),
        key=lambda r: (r.get("stake_pct") is None, -(r.get("stake_pct") or 0), r.get("ticker") or ""),
    )


async def governance_snapshot(
    ticker: str, db: AsyncSession, shareholder_limit: int = 5, insider_limit: int = 8
) -> dict[str, Any]:
    """특정 ticker의 최근 지배구조 스냅샷.

    최근 as_of 기준 TOP N. 데이터 없으면 해당 필드는 빈 배열 반환.
    """
    # 최근 as_of 1회차만
    latest_sh_res = await db.execute(
        select(MajorShareholder.as_of)
        .where(MajorShareholder.ticker == ticker)
        .order_by(MajorShareholder.as_of.desc())
        .limit(1)
    )
    latest_sh_as_of = latest_sh_res.scalar_one_or_none()
    shareholders: list[dict] = []
    if latest_sh_as_of:
        r = await db.execute(
            select(MajorShareholder)
            .where(
                MajorShareholder.ticker == ticker,
                MajorShareholder.as_of == latest_sh_as_of,
            )
            .order_by(MajorShareholder.stake_pct.desc().nullslast())
            .limit(shareholder_limit)
        )
        shareholders = [
            {
                "name": s.holder_name,
                "type": s.holder_type,
                "stake_pct": s.stake_pct,
                "shares": s.shares,
                "holder_ticker": s.holder_ticker,
            }
            for s in r.scalars().all()
        ]

    latest_in_res = await db.execute(
        select(Insider.as_of)
        .where(Insider.ticker == ticker)
        .order_by(Insider.as_of.desc())
        .limit(1)
    )
    latest_in_as_of = latest_in_res.scalar_one_or_none()
    insiders: list[dict] = []
    if latest_in_as_of:
        r = await db.execute(
            select(Insider)
            .where(Insider.ticker == ticker, Insider.as_of == latest_in_as_of)
            .order_by(Insider.is_registered.desc().nullslast(), Insider.person_name)
            .limit(insider_limit)
        )
        insiders = [
            {
                "name": i.person_name,
                "role": i.role,
                "classification": i.classification,
                "is_registered": i.is_registered,
                "own_shares": i.own_shares,
            }
            for i in r.scalars().all()
        ]

    # 부모·자회사 (SQL CorporateOwnership에서만 최근 as_of)
    parents_res = await db.execute(
        select(CorporateOwnership)
        .where(CorporateOwnership.child_ticker == ticker)
        .order_by(CorporateOwnership.as_of.desc())
        .limit(10)
    )
    parents = _dedupe_linked([
        {
            "ticker": p.parent_ticker,
            "name": p.parent_name,
            "stake_pct": p.stake_pct,
            "as_of": p.as_of,
        }
        for p in parents_res.scalars().all()
    ])
    children_res = await db.execute(
        select(CorporateOwnership)
        .where(CorporateOwnership.parent_ticker == ticker)
        .order_by(CorporateOwnership.as_of.desc())
        .limit(10)
    )
    children = _dedupe_linked([
        {
            "ticker": c.child_ticker,
            "name": c.child_name,
            "stake_pct": c.stake_pct,
            "as_of": c.as_of,
        }
        for c in children_res.scalars().all()
    ])

    # 회사명
    corp = (
        await db.execute(select(Company).where(Company.ticker == ticker))
    ).scalar_one_or_none()

    return {
        "ticker": ticker,
        "name": corp.name_ko if corp else None,
        "as_of": latest_sh_as_of or latest_in_as_of,
        "shareholders": shareholders,
        "insiders": insiders,
        "parents": parents,
        "children": children,
    }


async def detect_circular_ownership_sql(
    ticker: str, db: AsyncSession, max_depth: int = 5
) -> list[list[str]]:
    """SQL 내 CorporateOwnership에서 ticker를 포함하는 순환 고리 탐색.

    Neo4j 없는 환경 fallback. 최근 as_of 기준 edge만 사용.
    DFS로 cycle 탐지 (깊이 max_depth 제한).
    """
    # 최근 as_of edges만
    res = await db.execute(
        select(CorporateOwnership.parent_ticker, CorporateOwnership.child_ticker)
    )
    edges = res.all()
    adj: dict[str, set[str]] = defaultdict(set)
    for parent, child in edges:
        if parent and child:
            adj[parent].add(child)

    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str], depth: int) -> None:
        if depth > max_depth:
            return
        for nb in adj.get(node, ()):
            if nb == ticker and len(path) > 1:
                cycles.append([*path, nb])
                continue
            if nb in path:
                continue  # 다른 경로에서 시작하는 루프는 여기서 리포트 안 함
            dfs(nb, [*path, nb], depth + 1)

    dfs(ticker, [ticker], 0)
    # 중복 제거 (정규화된 회전 형태)
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for c in cycles:
        # 사이클의 시작을 ticker에 고정 — 이미 그렇게 시작하므로 튜플 그대로 키
        key = tuple(c)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique

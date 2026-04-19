"""DART 지배구조 보고서 → 엔티티(인물·관계) 추출 + Neo4j / SQL upsert.

파이프라인 (Phase 2, 2026-04-19):
1. 대상 ticker 선정 → Disclosure 중 '지배구조/임원/주요주주' 키워드 매칭
2. DART document.xml (zip) fetch → 내부 HTML decode → 태그 제거 → 본문 텍스트
3. 공시 1건당 Claude tool_use 1회 호출 — 본문 8000자 + 제목/회사/일자 context
4. persons / corporate_shareholders 배열 → confidence ≥ 0.5 필터 + 중복 병합
5. SQL 3테이블 upsert (MajorShareholder · Insider · CorporateOwnership)
   + Neo4j (Person)-[LEADS/HOLDS]->(Company) / (Company)-[HOLDS_SHARES]->(Company)

Phase 1 skeleton (제목만 LLM 에 넘김) → Phase 2 (본문 fetch) 업그레이드.
본문 확보 후부터는 대표이사·사외이사·최대주주 지분율 등 구체 값 추출 가능.
"""
import asyncio
import io
import logging
import re
import zipfile
from datetime import datetime
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.database import async_session
from app.models.tables import (
    Company,
    CorporateOwnership,
    Disclosure,
    Insider,
    MajorShareholder,
)
from app.services.graph.client import run_cypher

logger = logging.getLogger(__name__)


DART_BASE = "https://opendart.fss.or.kr/api"


# 지배구조 관련 공시 키워드 (extract 대상). 사업·반기·분기보고서는 임원·최대주주
# 섹션이 표준 포함되므로 본문 있는 경우 가장 정보 밀도 높음.
GOVERNANCE_KEYWORDS = (
    "지배구조보고서",
    "임원·주요주주특정증권등소유상황보고서",
    "임원ㆍ주요주주특정증권등소유상황보고서",
    "최대주주등소유주식변동신고서",
    "주식등의대량보유상황보고서",
    "사외이사선임",
    "대표이사변경",
    "최대주주변경",
    "사업보고서",
    "반기보고서",
    "분기보고서",
)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _fetch_document_html(rcept_no: str, api_key: str) -> str:
    """DART document.xml (zip) → 내부 HTML 문자열. 실패 시 빈 문자열."""
    if not rcept_no:
        return ""
    try:
        r = requests.get(
            f"{DART_BASE}/document.xml",
            params={"crtfc_key": api_key, "rcept_no": rcept_no},
            timeout=20,
        )
        r.raise_for_status()
        data = r.content
        if not data.startswith(b"PK"):
            return ""
        zf = zipfile.ZipFile(io.BytesIO(data))
        names = zf.namelist()
        if not names:
            return ""
        raw = zf.open(names[0]).read()
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning("governance document.xml %s fetch failed: %s", rcept_no, e)
        return ""


def _html_to_text(html: str, max_chars: int = 8000) -> str:
    """HTML 태그 제거 + 공백 정규화. LLM 토큰 절감 위해 상한."""
    if not html:
        return ""
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]


# 법인명 정규화 — "삼성생명보험주식회사" ↔ "삼성생명보험" 같은 variant 를 동일 키로.
# "주식회사" 계열 법인체 suffix 만 제거 (업종 단어 '보험' 자체는 유지해야
# Company.name_ko "삼성생명보험" 과 매치됨).
_CORP_ENTITY_SUFFIX_RE = re.compile(
    r"(주식회사|\(주\)|㈜|co\.?,?\s*ltd\.?|inc\.?)",
    re.IGNORECASE,
)


def _normalize_corp_name(name: str) -> str:
    """법인명 dedup 키 — 공백·법인체 접미 제거, lower case."""
    if not name:
        return ""
    n = _CORP_ENTITY_SUFFIX_RE.sub("", name)
    n = re.sub(r"\s+", "", n)
    return n.lower().strip()


# 시장 우선순위 — 같은 이름에 여러 ticker 매칭 시 메인 상장을 고름
_MARKET_PRIORITY = {"KOSPI": 0, "KOSDAQ": 1, "KONEX": 2, "UNKNOWN": 3, None: 4}


async def _load_company_name_to_ticker() -> dict[str, list[tuple[str, str]]]:
    """Company 테이블 name_ko → 후보 [(ticker, normalized_name), ...] 맵.

    같은 정규화 이름을 가진 회사가 여러 ticker 로 등록된 경우(예: 000830
    '삼성물산' UNKNOWN + 028260 '삼성물산' KOSPI) 시장 우선순위 (KOSPI→
    KOSDAQ→KONEX→UNKNOWN) 로 정렬해 첫 요소가 메인 상장이 되도록 보장.
    """
    buckets: dict[str, list[tuple[str, str, str | None]]] = {}
    async with async_session() as db:
        r = await db.execute(select(Company.ticker, Company.name_ko, Company.market))
        for ticker, name, market in r.all():
            if not name:
                continue
            key = _normalize_corp_name(name)
            if not key:
                continue
            buckets.setdefault(key, []).append((ticker, key, market))

    # 시장 우선순위 + ticker 숫자 정렬 (KOSPI 메인이 앞으로)
    out: dict[str, list[tuple[str, str]]] = {}
    for key, rows in buckets.items():
        rows.sort(key=lambda x: (_MARKET_PRIORITY.get(x[2], 9), x[0]))
        out[key] = [(t, k) for (t, k, _m) in rows]
    return out


def _match_corp_ticker(name: str, name_map: dict[str, list[tuple[str, str]]]) -> str | None:
    """법인명 → ticker 매칭. 1) 정확 매칭 → 2) 부분 매칭 (길이비≥0.6).

    부분 매칭은 '삼성생명보험' ↔ '삼성생명' 같은 업종 단어 variant 커버.
    오탐 방지로 양방향 substring + 길이 비율 가드.
    """
    if not name:
        return None
    norm = _normalize_corp_name(name)
    if not norm:
        return None

    # 1. 정확 매칭 — 첫 후보가 시장 우선순위 최상위
    if norm in name_map:
        return name_map[norm][0][0]

    # 2. 부분 매칭 (한쪽이 다른 쪽을 포함 + 길이 비율 0.6 이상)
    best: tuple[str, float] | None = None
    for key, candidates in name_map.items():
        if len(key) < 3:
            continue  # 너무 짧은 토큰은 오탐 위험 ('sk', 'lg' 등)
        if key in norm or norm in key:
            ratio = min(len(key), len(norm)) / max(len(key), len(norm))
            if ratio >= 0.6 and (best is None or ratio > best[1]):
                best = (candidates[0][0], ratio)
    return best[0] if best else None


EXTRACT_TOOL = {
    "name": "extract_governance_entities",
    "description": (
        "공시 정보(특히 지배구조/임원·대주주)에서 인물·법인 주주·역할·지분 엔티티를 추출한다. "
        "추출 불가능하거나 정보 없음이면 빈 배열 반환."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "persons": {
                "type": "array",
                "description": "공시에 등장하는 인물 목록 (회장/대표/사외이사/대주주 등)",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "한국어 성명"},
                        "role": {
                            "type": "string",
                            "description": "역할 (예: 회장, 대표이사, 사외이사, 대주주, 감사)",
                        },
                        "relation": {
                            "type": "string",
                            "enum": ["LEADS", "HOLDS", "UNKNOWN"],
                        },
                        "stake_pct": {
                            "type": "number",
                            "description": "지분율 %. HOLDS일 때만, 없으면 0",
                        },
                        "classification": {
                            "type": "string",
                            "enum": ["exec", "outside", "audit", "unknown"],
                            "description": "임원 분류 — exec(등기/미등기임원), outside(사외이사), audit(감사·감사위원)",
                        },
                        "is_registered": {
                            "type": "boolean",
                            "description": "등기임원 여부. 모르면 null",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0.0~1.0 신뢰도",
                        },
                    },
                    "required": ["name", "role", "relation", "confidence"],
                },
            },
            "corporate_shareholders": {
                "type": "array",
                "description": "법인 주주 목록 — 타 상장사·지주사·해외법인 등",
                "items": {
                    "type": "object",
                    "properties": {
                        "corp_name": {"type": "string", "description": "법인명"},
                        "corp_ticker": {
                            "type": "string",
                            "description": "해당 법인의 한국 상장 ticker (알면). 없으면 빈 문자열",
                        },
                        "stake_pct": {
                            "type": "number",
                            "description": "지분율 %",
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": ["corp_name", "stake_pct", "confidence"],
                },
            },
        },
        "required": ["persons"],
    },
}


EXTRACT_SYSTEM = """한국 DART 공시 **본문** 에서 인물·법인 주주 엔티티를 추출하는 분석가다.
공시 제목 + 본문을 함께 읽고 구체적 성명·직책·지분율을 뽑아낸다.

규칙:
- 본문에 **명시적으로 등장한** 인물·법인만. 추론·상식 보충 금지.
- persons:
  * relation=LEADS — 대표이사·사내이사·사외이사·감사 등 이사회 구성원
  * relation=HOLDS — 개인 최대주주·주요주주 (본인 + 특수관계인 포함 가능)
  * classification: exec(등기/미등기 임원) · outside(사외이사) · audit(감사·감사위원) · unknown
  * is_registered: 등기임원이면 true, 미등기/모름이면 null 또는 false
- corporate_shareholders: 법인 주주 — 지주사·계열사·외국법인·국민연금 등 기관.
- confidence: 본문 명시도 기준 0.0~1.0. 지분율·직책이 명확하면 ≥0.8, 암시적이면 ≤0.6.
- 본문에서 확인 불가능한 필드는 0 또는 빈 문자열.
- 같은 인물이 본문에서 여러 번 언급되어도 1건만.
- 10명 이상 임원 명단은 등기임원·대표이사 우선 최대 10명까지.
"""


async def extract_from_disclosures(ticker: str, limit: int = 6) -> dict:
    """ticker의 governance 공시를 본문 fetch + LLM 추출.

    Phase 2 파이프라인:
    1. DB 에서 ticker 의 최근 공시 300건 → GOVERNANCE_KEYWORDS 매칭 → 최신 `limit` 건.
    2. 각 건 document.xml fetch → HTML→text → 8,000자 컨텍스트.
    3. 공시별 Claude tool_use 1회 호출, persons + corporate_shareholders 수집.
    4. 공시 간 중복 병합 (persons: (name,role) 기준 최고 confidence, corps: corp_name 기준).
    5. confidence ≥ 0.5 필터 → SQL upsert + Neo4j MERGE.
    """
    if not settings.anthropic_api_key:
        return {"status": "no_api_key"}
    if not settings.dart_api_key:
        return {"status": "no_dart_key"}

    async with async_session() as db:
        company_res = await db.execute(select(Company).where(Company.ticker == ticker))
        company = company_res.scalar_one_or_none()
        if not company:
            return {"status": "company_not_found"}

        disc_res = await db.execute(
            select(Disclosure)
            .where(Disclosure.ticker == ticker)
            .order_by(Disclosure.rcept_dt.desc())
            .limit(300)
        )
        all_disc = disc_res.scalars().all()

    # governance 키워드 매칭만 필터, 최신 순으로 limit
    gov = [d for d in all_disc if any(k in (d.report_nm or "") for k in GOVERNANCE_KEYWORDS)][:limit]
    if not gov:
        return {"status": "no_governance_disclosures", "ticker": ticker}

    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    loop = asyncio.get_event_loop()

    raw_persons: list[dict[str, Any]] = []
    raw_corps: list[dict[str, Any]] = []
    processed = 0
    empty_body = 0

    for d in gov:
        # 본문 fetch (blocking requests → thread)
        html = await loop.run_in_executor(
            None, _fetch_document_html, d.rcept_no or "", settings.dart_api_key
        )
        body = _html_to_text(html)
        if not body or len(body) < 300:
            empty_body += 1
            continue

        prompt = (
            f"회사: {company.name_ko} ({ticker})\n"
            f"공시일자: {d.rcept_dt}\n"
            f"공시 제목: {d.report_nm}\n"
            f"rcept_no: {d.rcept_no}\n\n"
            f"=== 공시 본문 ===\n{body}"
        )
        try:
            msg = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=3000,
                system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "extract_governance_entities"},
                timeout=60,
            )
        except Exception as e:
            logger.warning("governance claude call failed for %s/%s: %s", ticker, d.rcept_no, e)
            continue

        for block in msg.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "extract_governance_entities":
                raw_persons.extend(list(block.input.get("persons", [])))
                raw_corps.extend(list(block.input.get("corporate_shareholders", [])))
                break
        processed += 1

    # ticker 자동 매칭 (LLM 이 corp_ticker 공란으로 둔 법인명을 Company 테이블로 backfill)
    # 시장 우선순위 (KOSPI 메인) + fuzzy 매칭 (variant 이름 커버).
    name_to_ticker = await _load_company_name_to_ticker()
    for c in raw_corps:
        if not (c.get("corp_ticker") or "").strip():
            t = _match_corp_ticker(c.get("corp_name", ""), name_to_ticker)
            if t:
                c["corp_ticker"] = t

    # 공시 간 중복 병합 — 같은 사람 / 법인 여러 공시·variant 에 등장 시 최고 confidence 유지
    def _dedup_by(keys_fn, items):
        best: dict[tuple, dict] = {}
        for it in items:
            k = keys_fn(it)
            if not k or not k[0]:
                continue
            if k not in best or (it.get("confidence", 0) > best[k].get("confidence", 0)):
                best[k] = it
        return list(best.values())

    merged_persons = _dedup_by(
        lambda p: (str(p.get("name", "")).strip(), str(p.get("role", "")).strip()),
        raw_persons,
    )
    # 법인 dedup 키: 우선 corp_ticker (있으면 가장 신뢰), 없으면 정규화된 name
    def _corp_key(c: dict) -> tuple:
        t = (c.get("corp_ticker") or "").strip()
        if t:
            return ("T", t)
        return ("N", _normalize_corp_name(c.get("corp_name", "")))
    merged_corps = _dedup_by(_corp_key, raw_corps)

    accepted_persons = [p for p in merged_persons if p.get("confidence", 0) >= 0.5]
    accepted_corps = [c for c in merged_corps if c.get("confidence", 0) >= 0.5]
    persons = merged_persons  # 호환: 아래 upsert 루프에서 accepted_ 만 사용
    corporates = merged_corps
    as_of = datetime.utcnow().strftime("%Y-%m-%d")

    # Neo4j 동기화 (Person/Company 관계)
    for p in accepted_persons:
        person_id = f"p-{p['name'].strip().replace(' ', '-')}"
        await run_cypher(
            "MERGE (p:Person {id: $pid}) SET p.name_ko=$name, p.role=$role",
            {"pid": person_id, "name": p["name"], "role": p["role"]},
        )
        rel = p.get("relation", "UNKNOWN")
        if rel == "LEADS":
            await run_cypher(
                "MATCH (p:Person {id: $pid}) "
                "MATCH (c:Company {ticker: $t}) "
                "MERGE (p)-[r:LEADS]->(c) SET r.role=$role, r.source='dart-extractor'",
                {"pid": person_id, "t": ticker, "role": p["role"]},
            )
        elif rel == "HOLDS":
            await run_cypher(
                "MATCH (p:Person {id: $pid}) "
                "MATCH (c:Company {ticker: $t}) "
                "MERGE (p)-[r:HOLDS]->(c) "
                "SET r.pct=$pct, r.source='dart-extractor'",
                {"pid": person_id, "t": ticker, "pct": p.get("stake_pct", 0)},
            )

    # Company → Company 법인 지분 관계 (Neo4j + SQL 양방향)
    for cshare in accepted_corps:
        corp_ticker = (cshare.get("corp_ticker") or "").strip()
        if corp_ticker:
            await run_cypher(
                "MATCH (parent:Company {ticker: $parent}) "
                "MATCH (child:Company {ticker: $child}) "
                "MERGE (parent)-[r:HOLDS_SHARES]->(child) "
                "SET r.pct=$pct, r.as_of=$as_of, r.source='dart-extractor'",
                {
                    "parent": corp_ticker,
                    "child": ticker,
                    "pct": cshare.get("stake_pct", 0),
                    "as_of": as_of,
                },
            )

    # SQL 스냅샷 적립 — 당일 as_of 로 기존 행을 먼저 비운 뒤 fresh insert.
    # 이전 extraction 이 variant 이름(예: "삼성생명보험주식회사" vs "삼성생명")으로
    # 두 행을 남겼을 때 stale 행이 프론트에 중복 표시되던 문제 방지.
    # 최신 데이터가 확보된 경우에만 삭제 — 빈 추출로 기존 good 데이터 지우지 않음.
    from sqlalchemy import delete as sa_delete
    async with async_session() as db:
        if accepted_persons or accepted_corps:
            await db.execute(
                sa_delete(MajorShareholder).where(
                    MajorShareholder.ticker == ticker,
                    MajorShareholder.as_of == as_of,
                )
            )
            await db.execute(
                sa_delete(Insider).where(
                    Insider.ticker == ticker,
                    Insider.as_of == as_of,
                )
            )
            await db.execute(
                sa_delete(CorporateOwnership).where(
                    CorporateOwnership.child_ticker == ticker,
                    CorporateOwnership.as_of == as_of,
                )
            )

        for p in accepted_persons:
            rel = p.get("relation", "UNKNOWN")
            if rel == "HOLDS":
                await _upsert_shareholder(
                    db,
                    ticker=ticker,
                    holder_name=p["name"],
                    holder_type="person",
                    stake_pct=p.get("stake_pct"),
                    as_of=as_of,
                )
            elif rel == "LEADS":
                await _upsert_insider(
                    db,
                    ticker=ticker,
                    person_name=p["name"],
                    role=p["role"],
                    classification=p.get("classification"),
                    is_registered=p.get("is_registered"),
                    as_of=as_of,
                )
        # corp → canonical name 으로 upsert 해서 dedup 보장.
        # holder_ticker 있으면 Company.name_ko 가 canonical, 없으면 LLM 이름.
        name_by_ticker = {
            c.ticker: c.name_ko
            for c in (
                await db.execute(
                    select(Company).where(
                        Company.ticker.in_(
                            [
                                (c.get("corp_ticker") or "").strip()
                                for c in accepted_corps
                                if (c.get("corp_ticker") or "").strip()
                            ]
                        )
                    )
                )
            ).scalars().all()
        }
        for c in accepted_corps:
            corp_ticker = (c.get("corp_ticker") or "").strip() or None
            canonical = name_by_ticker.get(corp_ticker) if corp_ticker else None
            display_name = canonical or c["corp_name"]
            await _upsert_shareholder(
                db,
                ticker=ticker,
                holder_name=display_name,
                holder_type="corp",
                stake_pct=c.get("stake_pct"),
                holder_ticker=corp_ticker,
                as_of=as_of,
            )
            if corp_ticker:
                await _upsert_corp_ownership(
                    db,
                    parent_ticker=corp_ticker,
                    child_ticker=ticker,
                    parent_name=display_name,
                    child_name=company.name_ko,
                    stake_pct=c.get("stake_pct"),
                    as_of=as_of,
                )
        await db.commit()

    return {
        "status": "ok",
        "ticker": ticker,
        "filings_matched": len(gov),
        "filings_processed": processed,
        "filings_empty_body": empty_body,
        "candidates_persons": len(raw_persons),
        "merged_persons": len(merged_persons),
        "accepted_persons": len(accepted_persons),
        "candidates_corps": len(raw_corps),
        "merged_corps": len(merged_corps),
        "accepted_corps": len(accepted_corps),
    }


# DB 방언 중립 upsert — Postgres(pg_insert) / SQLite(sqlite_insert) 모두 on_conflict 지원
def _dialect_insert(db):
    name = db.bind.dialect.name if db.bind else db.get_bind().dialect.name
    return pg_insert if name == "postgresql" else sqlite_insert


async def _upsert_shareholder(
    db,
    *,
    ticker: str,
    holder_name: str,
    holder_type: str,
    as_of: str,
    stake_pct: float | None = None,
    shares: int | None = None,
    holder_ticker: str | None = None,
) -> None:
    ins = _dialect_insert(db)(MajorShareholder).values(
        ticker=ticker,
        holder_name=holder_name,
        holder_type=holder_type,
        stake_pct=stake_pct,
        shares=shares,
        holder_ticker=holder_ticker,
        as_of=as_of,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["ticker", "holder_name", "as_of"],
        set_={
            "holder_type": ins.excluded.holder_type,
            "stake_pct": ins.excluded.stake_pct,
            "shares": ins.excluded.shares,
            "holder_ticker": ins.excluded.holder_ticker,
        },
    )
    await db.execute(stmt)


async def _upsert_insider(
    db,
    *,
    ticker: str,
    person_name: str,
    role: str,
    as_of: str,
    classification: str | None = None,
    is_registered: bool | None = None,
    own_shares: int | None = None,
) -> None:
    ins = _dialect_insert(db)(Insider).values(
        ticker=ticker,
        person_name=person_name,
        role=role,
        classification=classification,
        is_registered=is_registered,
        own_shares=own_shares,
        as_of=as_of,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["ticker", "person_name", "role", "as_of"],
        set_={
            "classification": ins.excluded.classification,
            "is_registered": ins.excluded.is_registered,
            "own_shares": ins.excluded.own_shares,
        },
    )
    await db.execute(stmt)


async def _upsert_corp_ownership(
    db,
    *,
    parent_ticker: str,
    child_ticker: str,
    as_of: str,
    parent_name: str | None = None,
    child_name: str | None = None,
    stake_pct: float | None = None,
) -> None:
    ins = _dialect_insert(db)(CorporateOwnership).values(
        parent_ticker=parent_ticker,
        child_ticker=child_ticker,
        parent_name=parent_name,
        child_name=child_name,
        stake_pct=stake_pct,
        as_of=as_of,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["parent_ticker", "child_ticker", "as_of"],
        set_={
            "parent_name": ins.excluded.parent_name,
            "child_name": ins.excluded.child_name,
            "stake_pct": ins.excluded.stake_pct,
        },
    )
    await db.execute(stmt)

"""공시/뉴스 본문에서 **기업간 관계**를 LLM 으로 추출해 Neo4j 엣지로 upsert.

seed_supply_chains.yaml 은 "널리 알려진" 공급 관계 seed, 이 추출기는 DART 공시
**본문**(document.xml HTML)에서 4종 관계를 자동 발견한다:

- `SUPPLIES`     — A 가 B 에 제품/서비스 공급 (수주·공급계약)
- `COMPETES_WITH`— A 와 B 는 동일 시장 경쟁 (사업보고서 경쟁 환경 기재)
- `OWNS`         — A 가 B 의 유의미한 지분 보유 (최대주주 변경·주식취득)
- `PARTNERS`     — A·B 공동사업 / JV / 전략적 제휴

필수 조건:
- DART document.xml ZIP fetch → HTML 파싱으로 **본문** 확보 (제목만으로는 관계
  추출 불가, Disclosure.summary_ko 가 비어있는 경우가 대부분).
- Postgres companies 테이블에서 회사명→ticker 매핑 후 미매칭은 버림.
- confidence < 0.6 버림, seed 엣지는 덮어쓰기 안 함.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import zipfile
from typing import Any

import requests

logger = logging.getLogger(__name__)


DART_BASE = "https://opendart.fss.or.kr/api"

EXTRACT_PROMPT = """너는 한국 상장사 공시 본문에서 **기업간 관계**만 추출하는 분석가다. 추론·추측 금지. 본문에 명시적으로 나온 관계만.

다음 4종 관계를 JSON 배열로 답하라 (빈 배열 가능):

- SUPPLIES      : A 가 B 에 제품/서비스/부품/장비/IP 를 공급 (수주, 단일판매·공급계약, 납품계약 등)
- COMPETES_WITH : A·B 가 동일 시장에서 경쟁 (사업 보고서의 경쟁 환경 기재)
- OWNS          : A 가 B 의 유의미한 지분 보유 (최대주주·주요주주 변경, 주식취득결정)
- PARTNERS      : A·B 공동사업·전략적 제휴·합작법인 (양방향성)

JSON 스키마 (pure JSON 배열, ```json 블록 없이):
[
  {
    "rel": "SUPPLIES|COMPETES_WITH|OWNS|PARTNERS",
    "a": "회사 A 정식 한국어명",
    "b": "회사 B 정식 한국어명",
    "role": "equipment|material|component|service|foundry|ip|unknown",   # SUPPLIES 만
    "pct": 0.0~100.0,                                                     # OWNS 만 (지분률)
    "evidence": "본문에서 발췌 1-2문장 (200자 이내)",
    "confidence": 0.0~1.0
  }
]

규칙:
- **방향성**: SUPPLIES 는 A→B (A 가 공급, B 가 고객). OWNS 는 A→B (A 가 지분 보유).
- **COMPETES_WITH/PARTNERS**: 알파벳·ticker 순 우선 (A<B) 으로 정규화해서 중복 방지.
- 계열사/지주회사·자회사 관계는 제외 (OWNS 는 **외부 지분** 만).
- 불확실하면 confidence 0.5 이하로.
- 3건 이상 추출 권장하지 않음 — 본문 핵심만.
"""


def _fetch_document_html(rcept_no: str, api_key: str) -> str:
    """공시 document.xml (zip) → 안쪽 HTML. 실패 시 빈 문자열."""
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
        logger.warning("document.xml %s fetch 실패: %s", rcept_no, e)
        return ""


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _html_to_text(html: str, max_chars: int = 6000) -> str:
    """HTML 태그 제거 + 공백 정규화. LLM 토큰 절약을 위해 상한."""
    if not html:
        return ""
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]


_PAREN_AND_SUFFIX = re.compile(r"[\(\)㈜]|\(주\)|주식회사|co\.,?\s*ltd\.?|inc\.?|\.", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    """회사명 → 소문자·공백제거·접미어제거 형태."""
    if not name:
        return ""
    n = _PAREN_AND_SUFFIX.sub("", name)
    return re.sub(r"\s+", "", n.lower()).strip()


def _match_ticker_by_name(name: str, name_to_ticker: dict[str, str]) -> str | None:
    if not name:
        return None
    # 1. 정확 매칭 (원본 정규화)
    norm = _normalize_name(name)
    if norm in name_to_ticker:
        return name_to_ticker[norm]
    # 2. 부분 매칭: 긴 이름이 DB의 짧은 이름을 포함할 때 (LG전자 in "LG전자(주)")
    #    또는 DB의 긴 이름이 추출 본문의 짧은 이름을 포함 (확실한 경우만)
    for db_key, ticker in name_to_ticker.items():
        # DB 키가 너무 짧으면 오탐 위험 (예: "SK" 가 "SK하이닉스"에 매치)
        if len(db_key) < 3:
            continue
        if db_key == norm or db_key in norm or norm in db_key:
            # 길이 비율 체크로 오탐 완화
            if min(len(db_key), len(norm)) / max(len(db_key), len(norm)) > 0.6:
                return ticker
    return None


async def _load_company_name_map() -> dict[str, str]:
    from app.database import async_session
    from app.models.market import Company
    from sqlalchemy import select

    out: dict[str, str] = {}
    async with async_session() as db:
        r = await db.execute(select(Company.ticker, Company.name_ko))
        for ticker, name in r.all():
            if not name:
                continue
            key = re.sub(r"\s+", "", name.lower())
            out.setdefault(key, ticker)
    return out


async def _call_claude(prompt_body: str) -> list[dict[str, Any]]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY missing — extractor skipped")
        return []
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("anthropic SDK not installed")
        return []
    client = AsyncAnthropic(api_key=api_key)
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2500,
            system=EXTRACT_PROMPT,
            messages=[{"role": "user", "content": prompt_body[:8000]}],
            timeout=45,
        )
        text = resp.content[0].text if resp.content else "[]"
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        return json.loads(m.group())
    except Exception as e:
        logger.warning("claude extract failed: %s", e)
        return []


# 관계 타입별 Cypher upsert 패턴
UPSERT_CYPHER = {
    "SUPPLIES": """
        MERGE (a:Company {ticker: $a_t})
          ON CREATE SET a.name_ko = $a_n
          ON MATCH  SET a.name_ko = coalesce(a.name_ko, $a_n)
        MERGE (b:Company {ticker: $b_t})
          ON CREATE SET b.name_ko = $b_n
          ON MATCH  SET b.name_ko = coalesce(b.name_ko, $b_n)
        MERGE (a)-[r:SUPPLIES]->(b)
          ON CREATE SET r.role = $role, r.source = 'extracted',
                        r.confidence = $conf, r.evidence_rcept_no = $rcept,
                        r.evidence = $evidence, r.created_at = datetime()
          ON MATCH SET  r.last_seen_at = datetime(),
                        r.confidence = CASE WHEN r.source = 'seed_supply_chains.yaml'
                                            THEN r.confidence
                                            ELSE $conf END
        """,
    "OWNS": """
        MERGE (a:Company {ticker: $a_t})
          ON CREATE SET a.name_ko = $a_n
        MERGE (b:Company {ticker: $b_t})
          ON CREATE SET b.name_ko = $b_n
        MERGE (a)-[r:OWNS]->(b)
          ON CREATE SET r.pct = $pct, r.source = 'extracted',
                        r.confidence = $conf, r.evidence_rcept_no = $rcept,
                        r.evidence = $evidence, r.created_at = datetime()
          ON MATCH SET  r.pct = $pct, r.last_seen_at = datetime(),
                        r.confidence = $conf
        """,
    "COMPETES_WITH": """
        MERGE (a:Company {ticker: $a_t})
          ON CREATE SET a.name_ko = $a_n
        MERGE (b:Company {ticker: $b_t})
          ON CREATE SET b.name_ko = $b_n
        MERGE (a)-[r:COMPETES_WITH]->(b)
          ON CREATE SET r.source = 'extracted', r.confidence = $conf,
                        r.evidence_rcept_no = $rcept, r.evidence = $evidence,
                        r.created_at = datetime()
          ON MATCH SET  r.last_seen_at = datetime(), r.confidence = $conf
        """,
    "PARTNERS": """
        MERGE (a:Company {ticker: $a_t})
          ON CREATE SET a.name_ko = $a_n
        MERGE (b:Company {ticker: $b_t})
          ON CREATE SET b.name_ko = $b_n
        MERGE (a)-[r:PARTNERS]->(b)
          ON CREATE SET r.source = 'extracted', r.confidence = $conf,
                        r.evidence_rcept_no = $rcept, r.evidence = $evidence,
                        r.created_at = datetime()
          ON MATCH SET  r.last_seen_at = datetime(), r.confidence = $conf
        """,
}


async def extract_supply_chains(
    days_back: int = 14,
    max_filings: int = 30,
    min_confidence: float = 0.6,
) -> dict[str, Any]:
    """공시 document.xml 본문에서 4종 관계 LLM 추출 → Neo4j upsert."""
    from datetime import date, timedelta
    from sqlalchemy import select
    from app.database import async_session
    from app.models.signals import Disclosure
    from app.services.graph.client import session as graph_session

    dart_key = os.environ.get("DART_API_KEY", "")
    if not dart_key:
        return {"error": "DART_API_KEY missing"}

    end = date.today()
    start = (end - timedelta(days=days_back)).isoformat()
    end_str = end.isoformat()

    # 관계 단서 있는 공시 키워드
    SIGNALS = [
        "단일판매", "공급계약", "공급 계약", "납품계약",
        "주식취득", "최대주주변경", "최대주주 변경",
        "합작", "전략적 제휴", "업무협약", "MOU",
    ]

    async with async_session() as db:
        q = (
            select(Disclosure)
            .where(Disclosure.rcept_dt >= start)
            .where(Disclosure.rcept_dt <= end_str)
            .order_by(Disclosure.rcept_dt.desc())
            .limit(max_filings * 3)
        )
        candidates = (await db.execute(q)).scalars().all()

    targets = [d for d in candidates if any(sig in (d.report_nm or "") for sig in SIGNALS)][:max_filings]
    logger.info("extract: %d candidates → %d targets", len(candidates), len(targets))

    if not targets:
        return {"processed": 0, "extracted": 0, "upserted": 0, "skipped": 0, "by_type": {}}

    name_map = await _load_company_name_map()

    upserted_by_type: dict[str, int] = {"SUPPLIES": 0, "OWNS": 0, "COMPETES_WITH": 0, "PARTNERS": 0}
    extracted_total = 0
    skipped = 0
    loop = asyncio.get_event_loop()

    # 디버깅: skip 이유별 카운터
    skip_reasons: dict[str, int] = {"low_conf": 0, "bad_rel": 0, "no_ticker": 0, "same_co": 0, "bad_shape": 0}

    async with graph_session(read_only=False) as s:
        for d in targets:
            # document.xml fetch (blocking requests → thread)
            html = await loop.run_in_executor(
                None, _fetch_document_html, d.rcept_no or "", dart_key
            )
            body_text = _html_to_text(html)
            if not body_text or len(body_text) < 200:
                # 본문이 너무 짧으면 제목만으로는 의미 없음 — skip
                continue
            full_context = f"공시 제목: {d.report_nm}\n소유사(ticker): {d.ticker}\n\n본문:\n{body_text}"
            results = await _call_claude(full_context)
            extracted_total += len(results)

            for r in results:
                try:
                    rel = r.get("rel", "").upper()
                    a_name = r.get("a", "")
                    b_name = r.get("b", "")
                    conf = float(r.get("confidence", 0))
                    evidence = (r.get("evidence") or "")[:500]
                except Exception:
                    skipped += 1
                    skip_reasons["bad_shape"] += 1
                    continue
                if rel not in UPSERT_CYPHER:
                    skipped += 1
                    skip_reasons["bad_rel"] += 1
                    logger.info("skip bad_rel=%s a=%r b=%r", rel, a_name, b_name)
                    continue
                if conf < min_confidence:
                    skipped += 1
                    skip_reasons["low_conf"] += 1
                    continue
                a_t = _match_ticker_by_name(a_name, name_map)
                b_t = _match_ticker_by_name(b_name, name_map)
                if not a_t or not b_t:
                    skipped += 1
                    skip_reasons["no_ticker"] += 1
                    logger.info("skip no_ticker a=%r→%s b=%r→%s", a_name, a_t, b_name, b_t)
                    continue
                if a_t == b_t:
                    skipped += 1
                    skip_reasons["same_co"] += 1
                    continue

                # COMPETES_WITH / PARTNERS 는 ticker 사전식 작은 쪽→큰 쪽 으로 정규화
                if rel in ("COMPETES_WITH", "PARTNERS") and a_t > b_t:
                    a_t, b_t = b_t, a_t
                    a_name, b_name = b_name, a_name

                params = {
                    "a_t": a_t, "a_n": a_name,
                    "b_t": b_t, "b_n": b_name,
                    "conf": conf,
                    "rcept": d.rcept_no or "",
                    "evidence": evidence,
                }
                if rel == "SUPPLIES":
                    params["role"] = r.get("role", "unknown")
                elif rel == "OWNS":
                    try:
                        params["pct"] = float(r.get("pct", 0))
                    except Exception:
                        params["pct"] = 0.0

                await s.run(UPSERT_CYPHER[rel], **params)
                upserted_by_type[rel] += 1

    total_upserted = sum(upserted_by_type.values())
    logger.info(
        "extract: processed=%d extracted=%d upserted=%d skipped=%d by_type=%s skip_reasons=%s",
        len(targets), extracted_total, total_upserted, skipped, upserted_by_type, skip_reasons,
    )
    return {
        "processed": len(targets),
        "extracted": extracted_total,
        "upserted": total_upserted,
        "skipped": skipped,
        "by_type": upserted_by_type,
        "skip_reasons": skip_reasons,
    }

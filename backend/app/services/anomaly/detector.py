"""공시 이상징후 탐지.

2단계 전략:
1. **규칙 기반 1차 필터** — report_nm 키워드로 고위험 공시 선별 (비용 0, 빠름)
2. **LLM 2차 판정** — 필터 통과한 건만 Claude에 넘겨 severity + reason 결정

규칙 전용 모드도 지원 (ANTHROPIC_API_KEY 없을 때).
"""
import logging
import json

from sqlalchemy import case, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import Disclosure, DisclosureEvidence

logger = logging.getLogger(__name__)

# 규칙 기반 severity 매핑 (report_nm 부분일치)
HIGH_KEYWORDS = [
    "감사의견거절", "감사의견한정", "계속기업 존속",
    "회생절차", "상장폐지", "횡령", "배임",
    "유상증자결정", "전환사채", "소송",
]
MED_KEYWORDS = [
    "최대주주변경", "주요사항보고", "자기주식", "분할", "합병",
    "주식교환", "무상증자", "공개매수",
]
RULE_SET_VERSION = "anomaly-keywords-v1"
LLM_MODEL = "claude-haiku-4-5-20251001"
PROMPT_VERSION = "severity-refine-v1"


SEVERITY_LABELS = {
    "high": "높음",
    "med": "중간",
    "low": "낮음",
    "uncertain": "확인 필요",
}


def build_title_summary(disclosure: Disclosure) -> str:
    """Build a conservative Korean summary from audited fields.

    This is intentionally extractive: it avoids inventing facts from a filing
    body we have not parsed yet, while keeping recent disclosure cards useful
    even when LLM summarization has not run.
    """
    title = (disclosure.report_nm or "공시").strip()
    ticker = (disclosure.ticker or "").strip()
    date = (disclosure.rcept_dt or "").strip()
    severity = (disclosure.anomaly_severity or "uncertain").lower()
    label = SEVERITY_LABELS.get(severity, "확인 필요")
    reason = (disclosure.anomaly_reason or "").strip()

    subject = f"{ticker} 종목" if ticker else "해당 회사"
    parts = [f"{date} {subject}이(가) '{title}' 공시를 제출했습니다."]
    if severity:
        parts.append(f"현재 제목 기반 중요도는 {label}입니다.")
    if reason and reason != "규칙 매칭 없음":
        parts.append(f"분류 근거: {reason}.")
    parts.append("세부 조건과 수치는 DART 원문에서 확인해야 합니다.")
    return " ".join(part for part in parts if part).strip()


def rule_based_match(report_nm: str) -> tuple[str | None, str | None, dict | None]:
    for kw in HIGH_KEYWORDS:
        if kw in report_nm:
            return "high", f"키워드 매칭: '{kw}'", {
                "type": "keyword_match",
                "keyword": kw,
                "source": "report_nm",
                "text": report_nm,
                "rule_set": RULE_SET_VERSION,
            }
    for kw in MED_KEYWORDS:
        if kw in report_nm:
            return "med", f"키워드 매칭: '{kw}'", {
                "type": "keyword_match",
                "keyword": kw,
                "source": "report_nm",
                "text": report_nm,
                "rule_set": RULE_SET_VERSION,
            }
    return None, None, {
        "type": "title_rule_scan",
        "matched": False,
        "source": "report_nm",
        "text": report_nm,
        "rule_set": RULE_SET_VERSION,
    }


def rule_based_severity(report_nm: str) -> tuple[str | None, str | None]:
    sev, reason, _ = rule_based_match(report_nm)
    return sev, reason


async def _llm_refine(report_nm: str, base_severity: str, base_reason: str) -> tuple[str, str]:
    """Claude로 severity 재확인. 키 없으면 규칙 결과 그대로."""
    if not settings.anthropic_api_key:
        return base_severity, base_reason
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=LLM_MODEL,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"한국 DART 공시 제목을 보고 투자자 관점의 심각도를 판정해. "
                    f"'high'(투자자 직격)/'med'(유의)/'low'(일상)로 한 단어, "
                    f"이어서 한국어 한 문장 이유.\n\n"
                    f"제목: {report_nm}\n"
                    f"규칙 판정: {base_severity} ({base_reason})\n\n"
                    f"severity 선택지: high / med / low / **uncertain**(정보 부족).\n"
                    f"형식: <severity>|<한국어 이유 한 문장>"
                ),
            }],
        )
        text = msg.content[0].text.strip()
        if "|" in text:
            sev, reason = text.split("|", 1)
            sev = sev.strip().lower()
            if sev in ("low", "med", "high", "uncertain"):
                return sev, reason.strip()
    except Exception as e:
        logger.warning(f"LLM refine failed: {e}")
    return base_severity, base_reason


async def _upsert_evidence(
    db: AsyncSession,
    *,
    rcept_no: str,
    kind: str,
    method: str,
    items: list[dict],
    model: str | None = None,
    prompt_version: str | None = None,
) -> None:
    result = await db.execute(
        select(DisclosureEvidence).where(
            DisclosureEvidence.rcept_no == rcept_no,
            DisclosureEvidence.kind == kind,
        )
    )
    evidence = result.scalar_one_or_none()
    payload = json.dumps(items, ensure_ascii=False)
    if evidence:
        evidence.method = method
        evidence.evidence_json = payload
        evidence.model = model
        evidence.prompt_version = prompt_version
        return
    db.add(DisclosureEvidence(
        rcept_no=rcept_no,
        kind=kind,
        method=method,
        evidence_json=payload,
        model=model,
        prompt_version=prompt_version,
    ))


async def scan_new_disclosures() -> dict:
    """severity 미판정 공시를 스캔하여 severity + reason 채움."""
    scanned = 0
    flagged = 0
    async with async_session() as db:
        result = await db.execute(
            select(Disclosure)
            .where(Disclosure.anomaly_severity.is_(None))
            .limit(1000)  # 대량 backfill 대비. LLM 호출 비용은 Haiku라 감당 가능
        )
        rows = result.scalars().all()
        for d in rows:
            scanned += 1
            sev, reason, evidence = rule_based_match(d.report_nm)
            if sev is None:
                d.anomaly_severity = "low"
                d.anomaly_reason = "규칙 매칭 없음"
                if not d.summary_ko:
                    d.summary_ko = build_title_summary(d)
                await _upsert_evidence(
                    db,
                    rcept_no=d.rcept_no,
                    kind="severity",
                    method="rule",
                    items=[evidence] if evidence else [],
                )
                continue
            final_sev, final_reason = await _llm_refine(d.report_nm, sev, reason)
            d.anomaly_severity = final_sev
            d.anomaly_reason = final_reason
            if not d.summary_ko:
                d.summary_ko = build_title_summary(d)
            llm_enabled = bool(settings.anthropic_api_key)
            await _upsert_evidence(
                db,
                rcept_no=d.rcept_no,
                kind="severity",
                method="rule+llm" if llm_enabled else "rule",
                items=[evidence] if evidence else [],
                model=LLM_MODEL if llm_enabled else None,
                prompt_version=PROMPT_VERSION if llm_enabled else None,
            )
            flagged += 1
        await db.commit()

    logger.info(f"Anomaly scan: {scanned} scanned, {flagged} flagged")
    return {"scanned": scanned, "flagged": flagged}


async def backfill_missing_evidence(limit: int = 5000) -> dict:
    """기존 severity 판정 공시에 누락된 근거를 채운다.

    과거 데이터는 `anomaly_severity`만 있고 evidence row가 없을 수 있다.
    LLM을 다시 호출하지 않고 현재 제목 규칙으로 재현 가능한 audit trail을 남긴다.
    """
    scanned = 0
    backfilled = 0
    remaining = max(0, limit)
    batch_size = 1000
    async with async_session() as db:
        while remaining > 0:
            missing_evidence = ~exists(
                select(1)
                .select_from(DisclosureEvidence)
                .where(
                    DisclosureEvidence.rcept_no == Disclosure.rcept_no,
                    DisclosureEvidence.kind == "severity",
                )
            )
            result = await db.execute(
                select(Disclosure)
                .where(
                    Disclosure.anomaly_severity.is_not(None),
                    missing_evidence,
                )
                .order_by(
                    case((Disclosure.anomaly_severity.in_(("high", "med")), 0), else_=1),
                    Disclosure.rcept_dt.desc(),
                )
                .limit(min(batch_size, remaining))
            )
            rows = result.scalars().all()
            if not rows:
                break
            for d in rows:
                scanned += 1
                _sev, _reason, evidence = rule_based_match(d.report_nm)
                await _upsert_evidence(
                    db,
                    rcept_no=d.rcept_no,
                    kind="severity",
                    method="rule_backfill",
                    items=[evidence] if evidence else [],
                )
                backfilled += 1
            await db.commit()
            remaining -= len(rows)

    logger.info("Disclosure evidence backfill: %s scanned, %s backfilled", scanned, backfilled)
    return {"scanned": scanned, "backfilled": backfilled, "limit": limit}


async def backfill_missing_summaries(limit: int = 5000) -> dict:
    """Backfill missing disclosure summaries with conservative title summaries."""
    scanned = 0
    backfilled = 0
    async with async_session() as db:
        result = await db.execute(
            select(Disclosure)
            .where(Disclosure.summary_ko.is_(None))
            .order_by(Disclosure.rcept_dt.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        for d in rows:
            scanned += 1
            d.summary_ko = build_title_summary(d)
            backfilled += 1
        await db.commit()

    logger.info("Disclosure summary backfill: %s scanned, %s backfilled", scanned, backfilled)
    return {"scanned": scanned, "backfilled": backfilled, "limit": limit}

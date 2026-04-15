"""공시 이상징후 탐지.

2단계 전략:
1. **규칙 기반 1차 필터** — report_nm 키워드로 고위험 공시 선별 (비용 0, 빠름)
2. **LLM 2차 판정** — 필터 통과한 건만 Claude에 넘겨 severity + reason 결정

규칙 전용 모드도 지원 (ANTHROPIC_API_KEY 없을 때).
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import Disclosure

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


def rule_based_severity(report_nm: str) -> tuple[str | None, str | None]:
    for kw in HIGH_KEYWORDS:
        if kw in report_nm:
            return "high", f"키워드 매칭: '{kw}'"
    for kw in MED_KEYWORDS:
        if kw in report_nm:
            return "med", f"키워드 매칭: '{kw}'"
    return None, None


async def _llm_refine(report_nm: str, base_severity: str, base_reason: str) -> tuple[str, str]:
    """Claude로 severity 재확인. 키 없으면 규칙 결과 그대로."""
    if not settings.anthropic_api_key:
        return base_severity, base_reason
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"한국 DART 공시 제목을 보고 투자자 관점의 심각도를 판정해. "
                    f"'high'(투자자 직격)/'med'(유의)/'low'(일상)로 한 단어, "
                    f"이어서 한국어 한 문장 이유.\n\n"
                    f"제목: {report_nm}\n"
                    f"규칙 판정: {base_severity} ({base_reason})\n\n"
                    f"형식: <severity>|<한국어 이유 한 문장>"
                ),
            }],
        )
        text = msg.content[0].text.strip()
        if "|" in text:
            sev, reason = text.split("|", 1)
            sev = sev.strip().lower()
            if sev in ("low", "med", "high"):
                return sev, reason.strip()
    except Exception as e:
        logger.warning(f"LLM refine failed: {e}")
    return base_severity, base_reason


async def scan_new_disclosures() -> dict:
    """severity 미판정 공시를 스캔하여 severity + reason 채움."""
    scanned = 0
    flagged = 0
    async with async_session() as db:
        result = await db.execute(
            select(Disclosure)
            .where(Disclosure.anomaly_severity.is_(None))
            .limit(200)
        )
        rows = result.scalars().all()
        for d in rows:
            scanned += 1
            sev, reason = rule_based_severity(d.report_nm)
            if sev is None:
                d.anomaly_severity = "low"
                d.anomaly_reason = "규칙 매칭 없음"
                continue
            final_sev, final_reason = await _llm_refine(d.report_nm, sev, reason)
            d.anomaly_severity = final_sev
            d.anomaly_reason = final_reason
            flagged += 1
        await db.commit()

    logger.info(f"Anomaly scan: {scanned} scanned, {flagged} flagged")
    return {"scanned": scanned, "flagged": flagged}

"""AI DD 메모 생성 파이프라인.

입력: ticker
컨텍스트 수집 순서:
1. Company 기본 정보
2. 최근 90일 공시 (요약 + severity)
3. 최근 30일 뉴스 (top 20, sentiment 가중)
4. (Phase 2) 실적 콜 transcript

출력: bull / bear / thesis 세 블록 + sources.json

버전 관리: DDMemo 1건 당 N개 DDMemoVersion 누적.
"""
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import Company, DDMemo, DDMemoVersion, Disclosure, NewsItem

logger = logging.getLogger(__name__)

MEMO_SYSTEM = """너는 한국 주식을 분석하는 DD(Due Diligence) 애널리스트다.
주어진 컨텍스트(공시/뉴스/기본정보)만을 근거로 bull/bear/thesis 3섹션 한국어 메모를 작성한다.

규칙:
- 각 주장 뒤에 [출처: rcept_no=YYYYxxxx] 형식으로 각주.
- 근거 없는 가격 타겟·매수추천 금지 (정보 제공만).
- **"투자자문 아님" 같은 disclaimer/경고 문구를 메모 본문에 포함하지 말 것.** (UI 푸터에 별도 표시됨)
- 각 섹션 본문은 순수 분석 내용만. blockquote·⚠️ 경고 금지.
- `submit_dd_memo` 도구를 호출해 구조화 제출. 마크다운 bullets/bold는 자유롭게 사용.
"""


MEMO_TOOL = {
    "name": "submit_dd_memo",
    "description": (
        "Bull/Bear/Thesis 3섹션을 구조화하여 제출. 각 섹션은 Markdown 형식 한국어. "
        "섹션 마커(## BULL 등) 붙이지 말고 본문만."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "bull": {
                "type": "string",
                "description": "Bull 논리 (긍정적 관점). 3~5개 bullet + 각주. Markdown.",
            },
            "bear": {
                "type": "string",
                "description": "Bear 논리 (부정적 관점). 3~5개 bullet + 각주. Markdown.",
            },
            "thesis": {
                "type": "string",
                "description": (
                    "투자 관점 종합 결론. **2~4 문단으로 나누어 작성**. "
                    "각 문단은 2~3 문장. 문단 사이는 빈 줄(`\\n\\n`)로 명확히 분리. "
                    "장문 한 덩어리 금지 — 편집자가 읽기 좋게 호흡 조절."
                ),
            },
        },
        "required": ["bull", "bear", "thesis"],
    },
}


async def _gather_context(ticker: str, db: AsyncSession) -> dict:
    company_res = await db.execute(select(Company).where(Company.ticker == ticker))
    company = company_res.scalar_one_or_none()

    since = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    disc_res = await db.execute(
        select(Disclosure)
        .where(Disclosure.ticker == ticker, Disclosure.rcept_dt >= since)
        .order_by(Disclosure.rcept_dt.desc())
        .limit(30)
    )
    disclosures = disc_res.scalars().all()

    news_cutoff = datetime.utcnow() - timedelta(days=30)
    news_res = await db.execute(
        select(NewsItem)
        .where(NewsItem.ticker == ticker, NewsItem.published_at >= news_cutoff)
        .order_by(NewsItem.published_at.desc())
        .limit(20)
    )
    news = news_res.scalars().all()

    return {"company": company, "disclosures": disclosures, "news": news}


def _format_context(ctx: dict) -> str:
    c = ctx["company"]
    lines = []
    if c:
        lines.append(f"# 기업: {c.name_ko} ({c.ticker}) · {c.market} · {c.sector or '-'}")
    lines.append("\n## 최근 공시")
    for d in ctx["disclosures"]:
        sev = f"[{d.anomaly_severity}]" if d.anomaly_severity else ""
        lines.append(f"- {d.rcept_dt} {sev} {d.report_nm} (rcept_no={d.rcept_no})")
    lines.append("\n## 최근 뉴스")
    for n in ctx["news"]:
        lines.append(f"- {n.published_at.date()} {n.source}: {n.title}")
    return "\n".join(lines)


def _parse_memo(text: str) -> dict:
    sections = {"bull": "", "bear": "", "thesis": ""}
    current = None
    for line in text.splitlines():
        s = line.strip().upper()
        if s.startswith("## BULL"):
            current = "bull"
            continue
        if s.startswith("## BEAR"):
            current = "bear"
            continue
        if s.startswith("## THESIS"):
            current = "thesis"
            continue
        if current:
            sections[current] += line + "\n"
    return {k: v.strip() for k, v in sections.items()}


# 금지어: 투자자문·추천성 표현 (Amodei guardrail)
FORBIDDEN_WORDS = ("목표가", "매수 추천", "매도 추천", "보유 추천", "Strong Buy", "strong buy")


def _has_forbidden_words(text: str) -> tuple[bool, str]:
    for w in FORBIDDEN_WORDS:
        if w in text:
            return True, w
    return False, ""


def _validate_citations(text: str, valid_rcept_nos: set[str]) -> tuple[bool, list[str]]:
    """각주의 rcept_no가 실제 db에 존재하는지 검증. 없으면 fabrication (LeCun)."""
    import re
    cited = set(re.findall(r"rcept_no=(\d+)", text))
    fake = [c for c in cited if c not in valid_rcept_nos]
    return len(fake) == 0, fake


async def generate_memo(ticker: str, user_id: str | None = None, _retry: int = 0) -> dict:
    """신규 DDMemoVersion 생성.

    BYOK: user_id 제공 + 해당 유저 byok_anthropic_key 등록 → 그 키 사용,
    없으면 서버 .env ANTHROPIC_API_KEY 사용. 둘 다 없으면 503.

    Guardrails:
    - 금지어(목표가·추천) 발견 시 1회 재생성
    - 각주 rcept_no의 fabrication 검증, 발견 시 1회 재생성
    - 재생성 2회 후에도 실패하면 마지막 출력 저장 + warning 반환
    """
    from sqlalchemy import select
    from app.models.tables import User
    from app.services.llm_client import get_anthropic_client

    user_obj = None
    if user_id:
        async with async_session() as db:
            user_obj = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    client, key_owner = await get_anthropic_client(user_obj, kind="memo")

    async with async_session() as db:
        ctx = await _gather_context(ticker, db)
        if not ctx["company"]:
            raise ValueError(f"Company not found: {ticker}")
        prompt = _format_context(ctx)

        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=MEMO_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            tools=[MEMO_TOOL],
            tool_choice={"type": "tool", "name": "submit_dd_memo"},
        )
        # Extract structured output from tool_use block
        parsed = {"bull": "", "bear": "", "thesis": ""}
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "submit_dd_memo":
                parsed = {
                    "bull": str(block.input.get("bull", "")),
                    "bear": str(block.input.get("bear", "")),
                    "thesis": str(block.input.get("thesis", "")),
                }
                break
        if not parsed["bull"]:
            # Fallback: legacy markdown section 파싱
            text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
            parsed = _parse_memo(text)

        # Guardrail 검증 (Amodei + LeCun)
        full_body = f"{parsed['bull']}\n{parsed['bear']}\n{parsed['thesis']}"
        bad_word, word = _has_forbidden_words(full_body)
        valid_rcepts = {d.rcept_no for d in ctx["disclosures"]}
        cite_ok, fake_rcepts = _validate_citations(full_body, valid_rcepts)
        warnings = []
        if bad_word:
            warnings.append(f"forbidden_word:{word}")
        if not cite_ok:
            warnings.append(f"fake_rcept_no:{','.join(fake_rcepts)}")

        if warnings and _retry < 2:
            logger.warning(f"memo guardrail retry {_retry + 1}: {warnings}")
            # 재귀 재시도 (재생성 강제)
            return await generate_memo(ticker, user_id=user_id, _retry=_retry + 1)

        # 메모 엔티티 upsert
        memo_res = await db.execute(
            select(DDMemo).where(DDMemo.ticker == ticker, DDMemo.user_id == user_id).limit(1)
        )
        memo = memo_res.scalar_one_or_none()
        if not memo:
            memo = DDMemo(ticker=ticker, user_id=user_id)
            db.add(memo)
            await db.flush()

        # 다음 버전 번호
        ver_res = await db.execute(
            select(DDMemoVersion).where(DDMemoVersion.memo_id == memo.id).order_by(DDMemoVersion.version.desc()).limit(1)
        )
        prev = ver_res.scalar_one_or_none()
        next_ver = (prev.version + 1) if prev else 1

        sources = [{"type": "disclosure", "rcept_no": d.rcept_no} for d in ctx["disclosures"]]
        sources += [{"type": "news", "url": n.url} for n in ctx["news"]]

        # 감사 3튜플 (Amodei): user_id + key_owner + model
        # key_owner 는 상단 get_anthropic_client()가 이미 결정 ('user:<id>' or 'server')
        generated_by = f"claude-sonnet-4-6|key={key_owner}|warn={','.join(warnings) or 'none'}"

        version = DDMemoVersion(
            memo_id=memo.id,
            version=next_ver,
            bull=parsed["bull"],
            bear=parsed["bear"],
            thesis=parsed["thesis"],
            sources=json.dumps(sources, ensure_ascii=False),
            generated_by=generated_by,
        )
        db.add(version)
        await db.flush()
        memo.latest_version_id = version.id
        await db.commit()

        return {
            "memo_id": memo.id,
            "version_id": version.id,
            "version": next_ver,
            "bull": parsed["bull"],
            "bear": parsed["bear"],
            "thesis": parsed["thesis"],
        }

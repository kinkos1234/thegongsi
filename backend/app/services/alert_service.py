"""알림 디스패처. stock-strategy에서 그대로 이식.

트리거는 공시 이상징후(severity)로 교체 예정.
"""
import asyncio
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tables import AlertConfig, AlertHistory, Disclosure

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"low": 0, "med": 1, "high": 2}


async def send_telegram(chat_id: str, message: str) -> bool:
    if not settings.telegram_bot_token:
        logger.warning("Telegram bot token not configured")
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("telegram send failed: %s", e)
            return False


async def send_slack(webhook_url: str, message: str) -> bool:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(webhook_url, json={"text": message}, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("slack send failed: %s", e)
            return False


SEVERITY_COLOR = {
    "high": 15548997,   # 빨강
    "med": 16753920,    # 주황
    "low": 3447003,     # 파랑
    "uncertain": 9807270,  # 회색
}

DART_VIEW_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
COMPANY_PAGE_URL = "https://thegongsi.vercel.app/c/{ticker}"

SEVERITY_EMOJI = {"high": "🔴", "med": "🟡", "low": "🔵", "uncertain": "⚪"}


async def send_discord(webhook_url: str, message: str) -> bool:
    """평문 content 전송 (user-level alert, Slack 포맷 호환)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(webhook_url, json={"content": message}, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("discord send failed: %s", e)
            return False


async def send_discord_embed(
    webhook_url: str,
    disclosure: Disclosure,
    company_name: str | None = None,
) -> bool:
    """Discord Embed 포맷으로 이상공시 1건 전송.

    - Severity 이모지 + 종목명 prefix: "🔴 삼성전자(005930) — 유상증자결정"
    - Title URL: DART 원문
    - 필드: Severity / 종목 / 접수일 / 회사페이지 링크(The Gongsi)
    """
    sev = (disclosure.anomaly_severity or "uncertain").lower()
    emoji = SEVERITY_EMOJI.get(sev, "⚪")
    ticker = disclosure.ticker or "—"
    report = disclosure.report_nm or "(제목 없음)"

    name_part = f"{company_name}({ticker})" if company_name else ticker
    title = f"{emoji} {name_part} — {report}"
    # Discord embed title limit 256자
    title = title[:250]

    embed = {
        "title": title,
        "url": DART_VIEW_URL.format(rcept_no=disclosure.rcept_no),
        "color": SEVERITY_COLOR.get(sev, 9807270),
        "fields": [
            {"name": "Severity", "value": sev.upper(), "inline": True},
            {"name": "종목", "value": name_part, "inline": True},
            {"name": "접수일", "value": disclosure.rcept_dt or "—", "inline": True},
        ],
        "footer": {"text": "The Gongsi · thegongsi.vercel.app"},
        "timestamp": (disclosure.fetched_at.isoformat() + "Z") if disclosure.fetched_at else None,
    }
    if disclosure.anomaly_reason:
        embed["description"] = disclosure.anomaly_reason[:1500]
    # 하단 링크: The Gongsi 종목 페이지 (원문과 별개로 맥락 탐색)
    if disclosure.ticker:
        embed.setdefault("fields", []).append({
            "name": "더공시 종목 페이지",
            "value": COMPANY_PAGE_URL.format(ticker=disclosure.ticker),
            "inline": False,
        })
    payload = {"embeds": [embed]}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(webhook_url, json=payload, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("discord embed send failed: %s", e)
            return False


async def send_alert(channel: str, target: str, message: str) -> bool:
    if channel == "telegram":
        return await send_telegram(target, message)
    if channel == "slack":
        return await send_slack(target, message)
    if channel == "discord":
        return await send_discord(target, message)
    return False


async def check_and_alert(db: AsyncSession) -> dict:
    """최근 24시간 내 이상징후 공시를 구독자 + 글로벌 admin webhook 에 알림.

    - 글로벌: `settings.discord_webhook_url` 이 설정되어 있으면 admin 채널로
      모든 med/high disclosure 를 Embed 로 브로드캐스트. 운영자 본인용.
    - 사용자별: AlertConfig 테이블의 각 row 로 Severity 임계치 이상 필터 후
      해당 채널(telegram/slack/discord)·target 에 평문 전송. BYOA 개념.
    """
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d")

    disclosures_result = await db.execute(
        select(Disclosure)
        .where(Disclosure.rcept_dt >= cutoff)
        .where(Disclosure.anomaly_severity.in_(["med", "high"]))
    )
    disclosures = disclosures_result.scalars().all()
    if not disclosures:
        return {"alerts_sent": 0, "reason": "no_anomalies"}

    configs_result = await db.execute(select(AlertConfig).where(AlertConfig.is_active == True))
    configs = configs_result.scalars().all()

    admin_webhook = settings.discord_webhook_url
    admin_sent = 0
    user_sent = 0

    # 종목명 prefetch — Disclosure.ticker → Company.name_ko 매핑
    name_map: dict[str, str] = {}
    if admin_webhook:
        from app.models.market import Company
        tickers = list({d.ticker for d in disclosures if d.ticker})
        if tickers:
            nr = await db.execute(select(Company.ticker, Company.name_ko).where(Company.ticker.in_(tickers)))
            for t, n in nr.all():
                if n:
                    name_map[t] = n

    for d in disclosures:
        # 1) Admin 글로벌 broadcast — high severity 만 (노이즈 방지).
        #    Discord webhook rate limit: 30/min — 한 번에 쏟으면 throttled.
        if admin_webhook and (d.anomaly_severity or "").lower() == "high":
            cname = name_map.get(d.ticker or "")
            if await send_discord_embed(admin_webhook, d, company_name=cname):
                admin_sent += 1
                await asyncio.sleep(0.5)  # 최소 간격

        # 2) User-level 구독자 (Severity 임계치 필터)
        for c in configs:
            if SEVERITY_ORDER.get(d.anomaly_severity, 0) < SEVERITY_ORDER.get(c.severity_threshold, 1):
                continue
            msg = (
                f"*DART 이상공시 [{d.anomaly_severity.upper()}]*\n"
                f"📄 {d.report_nm}\n"
                f"🏷 {d.ticker} · {d.rcept_dt}\n"
                f"{d.anomaly_reason or ''}"
            )
            if await send_alert(c.channel, c.channel_target, msg):
                db.add(AlertHistory(alert_config_id=c.id, alert_type="disclosure_anomaly", message=msg))
                user_sent += 1

    if user_sent:
        await db.commit()
    return {
        "alerts_sent": admin_sent + user_sent,
        "admin_broadcast": admin_sent,
        "user_subscribers": user_sent,
        "disclosures_scanned": len(disclosures),
    }

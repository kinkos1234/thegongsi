"""알림 디스패처. stock-strategy에서 그대로 이식.

트리거는 공시 이상징후(severity)로 교체 예정.
"""
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


async def send_discord(webhook_url: str, message: str) -> bool:
    """평문 content 전송 (user-level alert, Slack 포맷 호환)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(webhook_url, json={"content": message}, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("discord send failed: %s", e)
            return False


async def send_discord_embed(webhook_url: str, disclosure: Disclosure) -> bool:
    """Discord Embed 포맷으로 이상공시 1건 전송.

    Severity 별 색상 / DART 원문 링크 / 티커·날짜·reason 필드.
    webhook_url 은 추적에 사용하지 않고 직접 호출.
    """
    sev = (disclosure.anomaly_severity or "uncertain").lower()
    embed = {
        "title": disclosure.report_nm or "(제목 없음)",
        "url": DART_VIEW_URL.format(rcept_no=disclosure.rcept_no),
        "color": SEVERITY_COLOR.get(sev, 9807270),
        "fields": [
            {"name": "Severity", "value": sev.upper(), "inline": True},
            {"name": "Ticker", "value": disclosure.ticker or "—", "inline": True},
            {"name": "접수일", "value": disclosure.rcept_dt or "—", "inline": True},
        ],
        "footer": {"text": "The Gongsi · thegongsi.vercel.app"},
        "timestamp": (disclosure.fetched_at.isoformat() + "Z") if disclosure.fetched_at else None,
    }
    if disclosure.anomaly_reason:
        embed["description"] = disclosure.anomaly_reason[:1500]
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

    for d in disclosures:
        # 1) Admin 글로벌 broadcast (Embed 포맷)
        if admin_webhook:
            if await send_discord_embed(admin_webhook, d):
                admin_sent += 1

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

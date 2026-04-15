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
        resp = await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
        return resp.status_code == 200


async def send_slack(webhook_url: str, message: str) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json={"text": message})
        return resp.status_code == 200


async def send_discord(webhook_url: str, message: str) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json={"content": message})
        return resp.status_code in (200, 204)


async def send_alert(channel: str, target: str, message: str) -> bool:
    if channel == "telegram":
        return await send_telegram(target, message)
    if channel == "slack":
        return await send_slack(target, message)
    if channel == "discord":
        return await send_discord(target, message)
    return False


async def check_and_alert(db: AsyncSession) -> dict:
    """최근 24시간 내 이상징후 공시를 구독자에게 알림."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d")

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

    sent = 0
    for d in disclosures:
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
                sent += 1
    if sent:
        await db.commit()
    return {"alerts_sent": sent}

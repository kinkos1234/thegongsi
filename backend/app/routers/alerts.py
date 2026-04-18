from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import AlertConfig, AlertHistory, User
from app.routers import get_current_user

router = APIRouter()

_VALID_CHANNELS = {"telegram", "slack", "discord"}
_VALID_SEVERITY = {"high", "med", "low"}


class AlertConfigRequest(BaseModel):
    channel: str = Field(..., description="telegram | slack | discord")
    channel_target: str = Field(..., min_length=5, max_length=500)
    severity_threshold: str = Field("med", description="high | med | low")


@router.get("/")
async def list_alerts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertConfig).where(AlertConfig.user_id == user.id))
    return [
        {
            "id": c.id,
            "channel": c.channel,
            "target": c.channel_target,
            "severity": c.severity_threshold,
            "active": c.is_active,
        }
        for c in result.scalars().all()
    ]


@router.post("/")
async def create_alert(
    req: AlertConfigRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.channel not in _VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"허용 채널: {', '.join(sorted(_VALID_CHANNELS))}")
    if req.severity_threshold not in _VALID_SEVERITY:
        raise HTTPException(status_code=400, detail=f"허용 심각도: {', '.join(sorted(_VALID_SEVERITY))}")
    # target 포맷 최소 검증 — 채널별 prefix 및 길이
    tgt = req.channel_target.strip()
    if req.channel == "discord" and not tgt.startswith("https://discord.com/api/webhooks/"):
        raise HTTPException(status_code=400, detail="Discord webhook URL은 https://discord.com/api/webhooks/… 형식이어야 합니다.")
    if req.channel == "slack" and not tgt.startswith("https://hooks.slack.com/"):
        raise HTTPException(status_code=400, detail="Slack webhook URL은 https://hooks.slack.com/… 형식이어야 합니다.")
    if req.channel == "telegram" and not (tgt.startswith("-") or tgt.startswith("@") or tgt.isdigit()):
        raise HTTPException(status_code=400, detail="Telegram은 chat_id(숫자 · -숫자) 또는 @username 형식이어야 합니다.")
    config = AlertConfig(
        user_id=user.id,
        channel=req.channel,
        channel_target=req.channel_target,
        severity_threshold=req.severity_threshold,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return {"id": config.id}


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(AlertConfig).where(AlertConfig.id == alert_id, AlertConfig.user_id == user.id)
    )
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="없는 알림 설정입니다.")
    await db.delete(row)
    await db.commit()
    return {"status": "removed"}


@router.get("/history")
async def alert_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AlertHistory)
        .join(AlertConfig, AlertConfig.id == AlertHistory.alert_config_id)
        .where(AlertConfig.user_id == user.id)
        .order_by(AlertHistory.sent_at.desc())
        .limit(100)
    )
    return [
        {"type": h.alert_type, "message": h.message, "sent_at": h.sent_at.isoformat()}
        for h in result.scalars().all()
    ]

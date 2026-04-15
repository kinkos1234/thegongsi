from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import AlertConfig, AlertHistory, User
from app.routers import get_current_user

router = APIRouter()


class AlertConfigRequest(BaseModel):
    channel: str  # telegram, slack, discord
    channel_target: str
    severity_threshold: str = "med"


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

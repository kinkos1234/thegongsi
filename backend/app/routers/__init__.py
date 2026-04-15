"""JWT 전용 인증 의존성. 초대 토큰은 제거됨."""
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from app.config import settings
from app.database import get_db


async def get_current_user_optional(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None

    from app.models.tables import User
    result = await db.execute(select(User).where(User.id == payload.get("sub")))
    return result.scalar_one_or_none()


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_optional(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

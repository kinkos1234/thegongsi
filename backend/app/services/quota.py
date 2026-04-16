"""서버 키 fallback 사용자 쿼터.

BYOK가 없어서 관리자 서버 키로 호출하는 사용자 → 일일 쿼터 체크.
kind별 ('memo', 'ask') 개별 카운트.
관리자 기본값 .env로 조정: SERVER_KEY_DAILY_LIMIT_MEMO, *_ASK.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.tables import ServerKeyUsage

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


async def _get_usage(db: AsyncSession, user_id: str, date: str, kind: str) -> ServerKeyUsage | None:
    res = await db.execute(
        select(ServerKeyUsage).where(
            ServerKeyUsage.user_id == user_id,
            ServerKeyUsage.date == date,
            ServerKeyUsage.kind == kind,
        )
    )
    return res.scalar_one_or_none()


async def check_and_increment(user_id: str, kind: str) -> dict:
    """서버 키 호출 전 쿼터 체크 (원자적 증가).

    Returns:
        {"ok": True, "count": N, "limit": L}  — 호출 허용
        {"ok": False, "count": N, "limit": L} — 차단 (429 응답용)
    """
    from sqlalchemy import update as sql_update

    limit = settings.server_key_daily_limit_memo if kind == "memo" else settings.server_key_daily_limit_ask
    if limit <= 0:
        return {"ok": True, "count": 0, "limit": 0}

    today = _today_kst()
    async with async_session() as db:
        # 원자적 증가: UPDATE ... SET count = count + 1 WHERE count < limit
        usage = await _get_usage(db, user_id, today, kind)
        if usage:
            if usage.count >= limit:
                return {"ok": False, "count": usage.count, "limit": limit}
            result = await db.execute(
                sql_update(ServerKeyUsage)
                .where(
                    ServerKeyUsage.user_id == user_id,
                    ServerKeyUsage.date == today,
                    ServerKeyUsage.kind == kind,
                    ServerKeyUsage.count < limit,
                )
                .values(count=ServerKeyUsage.count + 1)
            )
            await db.commit()
            if result.rowcount == 0:
                return {"ok": False, "count": usage.count, "limit": limit}
            return {"ok": True, "count": usage.count + 1, "limit": limit}
        else:
            db.add(ServerKeyUsage(user_id=user_id, date=today, kind=kind, count=1))
            await db.commit()
            return {"ok": True, "count": 1, "limit": limit}


async def get_usage_summary(user_id: str) -> dict:
    today = _today_kst()
    async with async_session() as db:
        memo = await _get_usage(db, user_id, today, "memo")
        ask = await _get_usage(db, user_id, today, "ask")
    return {
        "date": today,
        "memo": {
            "used": memo.count if memo else 0,
            "limit": settings.server_key_daily_limit_memo,
        },
        "ask": {
            "used": ask.count if ask else 0,
            "limit": settings.server_key_daily_limit_ask,
        },
    }

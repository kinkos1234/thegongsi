"""LLM 클라이언트 resolver — BYOK 우선, 서버 키 폴백 + 쿼터.

- user.byok_anthropic_key 등록 → 그 키 사용 (쿼터 없음)
- settings.anthropic_api_key fallback → 서버 키 + 일일 쿼터 (admin 면제)
- 둘 다 없으면 RuntimeError
"""
import logging

from app.config import settings
from app.services import crypto

logger = logging.getLogger(__name__)


def resolve_anthropic_key(user=None) -> tuple[str | None, str]:
    """(api_key, owner) 반환. owner ∈ {'user:<id>', 'server', 'none'}"""
    if user is not None and getattr(user, "byok_anthropic_key", None):
        if crypto.is_configured():
            try:
                return crypto.decrypt(user.byok_anthropic_key), f"user:{user.id}"
            except Exception as e:
                logger.warning(f"BYOK decrypt failed for user {user.id}: {e}")
        else:
            logger.warning("BYOK present but FIELD_ENCRYPTION_KEY missing")
    if settings.anthropic_api_key:
        return settings.anthropic_api_key, "server"
    return None, "none"


async def get_anthropic_client(user=None, kind: str = "ask"):
    """AsyncAnthropic 클라이언트 + owner 반환.

    - BYOK 사용자: 쿼터 없음
    - server fallback 사용자: 쿼터 체크 (ADMIN_EMAILS 리스트는 면제)
    - 키 부재 또는 쿼터 초과 → RuntimeError
    """
    key, owner = resolve_anthropic_key(user)
    if not key:
        raise RuntimeError(
            "No Anthropic API key available. "
            "Set ANTHROPIC_API_KEY in .env or register BYOK via /settings"
        )
    if owner == "server" and user is not None:
        is_admin = (user.email or "").lower() in settings.admin_email_list
        if not is_admin:
            from app.services.quota import check_and_increment
            result = await check_and_increment(user.id, kind)
            if not result["ok"]:
                raise RuntimeError(
                    f"quota_exceeded: 서버 키 {kind} 쿼터 소진 "
                    f"({result['count']}/{result['limit']}/day). "
                    f"자기 키 등록은 /settings"
                )
    from anthropic import AsyncAnthropic
    return AsyncAnthropic(api_key=key), owner

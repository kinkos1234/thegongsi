"""LLM 클라이언트 resolver — BYOK 우선, 서버 키 폴백.

사용자가 로그인했고 BYOK가 등록돼 있으면 그 키 사용,
없으면 서버 .env의 ANTHROPIC_API_KEY 사용.
둘 다 없으면 None 반환 → 호출부에서 처리.
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


def get_anthropic_client(user=None):
    """AsyncAnthropic 인스턴스 + owner 반환. 키 없으면 raise."""
    key, owner = resolve_anthropic_key(user)
    if not key:
        raise RuntimeError(
            "No Anthropic API key available. "
            "Set ANTHROPIC_API_KEY in .env or register BYOK via /api/byok/"
        )
    from anthropic import AsyncAnthropic
    return AsyncAnthropic(api_key=key), owner

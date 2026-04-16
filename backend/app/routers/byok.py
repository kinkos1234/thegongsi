"""BYOK(Bring Your Own Key) 엔드포인트.

사용자가 Anthropic/OpenAI 자체 키를 저장 → 서버 DB에 암호화 보관.
Managed hosted 모드에서 LLM 비용을 사용자가 부담하는 구조.

보안:
- Fernet(AES-128-CBC + HMAC) 대칭키 암호화
- 서버 환경변수 FIELD_ENCRYPTION_KEY 미설정 시 503
- GET은 키 존재 여부만 반환(원문 노출 금지)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import User
from app.routers import get_current_user
from app.services import crypto

router = APIRouter()


class SetKeyRequest(BaseModel):
    anthropic_key: str | None = None
    openai_key: str | None = None


def _mask(encrypted: str | None) -> str | None:
    """암호화된 키를 복호화해서 뒤 4자리만 표시. 실패 시 '설정됨'."""
    if not encrypted:
        return None
    try:
        if crypto.is_configured():
            decrypted = crypto.decrypt(encrypted)
            if len(decrypted) >= 8:
                return f"{decrypted[:7]}…{decrypted[-4:]}"
    except Exception:
        pass
    return "설정됨"


@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    from app.config import settings
    from app.services.quota import get_usage_summary
    usage = await get_usage_summary(user.id)
    is_admin = (user.email or "").lower() in settings.admin_email_list
    return {
        "configured_server_side": crypto.is_configured(),
        "anthropic": bool(user.byok_anthropic_key),
        "openai": bool(user.byok_openai_key),
        "anthropic_hint": _mask(user.byok_anthropic_key),
        "openai_hint": _mask(user.byok_openai_key),
        "is_admin": is_admin,
        "server_fallback_usage": usage,
    }


class VerifyRequest(BaseModel):
    anthropic_key: str


import re

# Anthropic API 키 형식 엄격 검증: sk-ant-api##-(base64url)
_ANTHROPIC_KEY_RE = re.compile(r"^sk-ant-api\d{2}-[A-Za-z0-9_\-]{80,200}$")


@router.post("/verify")
async def verify_key(req: VerifyRequest):
    """BYOK 저장 전 Anthropic API 키 검증.

    1) 형식 검증 (정규식) — 즉시 거부
    2) 1-token ping — 실제 API에 유효한 키인지 확인 (최소 비용)
    """
    key = (req.anthropic_key or "").strip()
    if not _ANTHROPIC_KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="유효하지 않은 Anthropic 키 형식입니다 (sk-ant-api##-...).")
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=key, timeout=10.0)
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ok"}],
        )
        return {"valid": True, "model": msg.model}
    except Exception:
        # 내부 에러 상세 노출 금지
        raise HTTPException(status_code=400, detail="키 검증 실패: Anthropic API에서 키를 거부했습니다.")


@router.post("/")
async def set_keys(
    req: SetKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not crypto.is_configured():
        raise HTTPException(status_code=503, detail="서버에 FIELD_ENCRYPTION_KEY가 설정되지 않았습니다.")

    if req.anthropic_key is not None:
        user.byok_anthropic_key = crypto.encrypt(req.anthropic_key) if req.anthropic_key else None
    if req.openai_key is not None:
        user.byok_openai_key = crypto.encrypt(req.openai_key) if req.openai_key else None

    db.add(user)
    await db.commit()
    return {"status": "ok"}


@router.delete("/")
async def clear_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.byok_anthropic_key = None
    user.byok_openai_key = None
    db.add(user)
    await db.commit()
    return {"status": "cleared"}

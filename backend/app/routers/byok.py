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


@router.post("/verify")
async def verify_key(req: VerifyRequest):
    """BYOK 저장 전 Anthropic API 유효성 1-token 테스트."""
    if not req.anthropic_key or not req.anthropic_key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="유효하지 않은 키 형식")
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=req.anthropic_key)
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ok"}],
        )
        return {"valid": True, "model": msg.model}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"키 검증 실패: {e}")


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

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


@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    from app.services.quota import get_usage_summary
    usage = await get_usage_summary(user.id)
    return {
        "configured_server_side": crypto.is_configured(),
        "anthropic": bool(user.byok_anthropic_key),
        "openai": bool(user.byok_openai_key),
        "server_fallback_usage": usage,
    }


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

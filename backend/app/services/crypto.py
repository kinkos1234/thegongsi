"""필드 암호화 헬퍼. Fernet(AES-128-CBC + HMAC) 기반.

사용:
    키 생성 (1회):
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    .env에 FIELD_ENCRYPTION_KEY=... 저장
"""
from app.config import settings


def _fernet():
    from cryptography.fernet import Fernet
    if not settings.field_encryption_key:
        raise RuntimeError("FIELD_ENCRYPTION_KEY not configured")
    return Fernet(settings.field_encryption_key.encode())


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def is_configured() -> bool:
    return bool(settings.field_encryption_key)

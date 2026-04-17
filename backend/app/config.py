from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./comad_stock.db"
    dart_api_key: str = ""
    anthropic_api_key: str = ""
    neo4j_url: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"  # AuraDB Free는 인스턴스 ID가 DB 이름
    cors_origins: str = "http://localhost:3333"
    jwt_secret_key: str  # 필수 — .env에 JWT_SECRET_KEY 설정 필요
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72
    field_encryption_key: str = ""  # Fernet 키 (base64). 없으면 BYOK 저장 불가
    # BYOK 미설정 사용자가 서버 키로 호출 가능한 일일 한도 (0=무제한)
    server_key_daily_limit_memo: int = 3
    server_key_daily_limit_ask: int = 20
    # 쿼터 예외 — 호스트 본인/운영자 이메일 (쉼표 구분)
    admin_emails: str = ""

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]
    telegram_bot_token: str = ""
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""
    # GitHub Actions → /api/admin/jobs/{id} 트리거용 공유 비밀.
    # 비어 있으면 admin_jobs 라우터는 모든 요청을 503으로 거부 (프로덕션에서 반드시 설정).
    admin_jobs_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()

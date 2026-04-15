"""pgvector 임베딩 모델 (별도 파일 — pgvector 의존성 격리).

PostgreSQL + pgvector 확장 필요:
    CREATE EXTENSION IF NOT EXISTS vector;

SQLite 폴백 환경에서는 import 시점에 실패하지 않도록 지연 로드.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.tables import Base, gen_id

try:
    from pgvector.sqlalchemy import Vector
    _HAS_PGVECTOR = True
except ImportError:
    _HAS_PGVECTOR = False
    Vector = None  # type: ignore


if _HAS_PGVECTOR:
    class Embedding(Base):
        __tablename__ = "embeddings"

        id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
        source_type: Mapped[str] = mapped_column(String(20), index=True)  # disclosure, news, transcript
        source_id: Mapped[str] = mapped_column(String(20), index=True)    # rcept_no, news_id, ...
        chunk_idx: Mapped[int] = mapped_column(Integer, default=0)
        chunk_text: Mapped[str] = mapped_column(Text)
        vector: Mapped[list[float]] = mapped_column(Vector(3072))  # text-embedding-3-large
        model: Mapped[str] = mapped_column(String(50), default="text-embedding-3-large")
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
else:
    class Embedding:  # type: ignore
        """pgvector 미설치 — SQLite 개발 환경 플레이스홀더."""
        pass

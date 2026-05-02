"""DD 메모 + 버전."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import Base, gen_id, utc_now


class DDMemo(Base):
    __tablename__ = "dd_memos"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("users.id"), nullable=True, index=True
    )
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    latest_version_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    versions: Mapped[list["DDMemoVersion"]] = relationship(
        back_populates="memo",
        cascade="all, delete-orphan",
        order_by="DDMemoVersion.version.desc()",
    )


class DDMemoVersion(Base):
    __tablename__ = "dd_memo_versions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    memo_id: Mapped[str] = mapped_column(String(12), ForeignKey("dd_memos.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    bull: Mapped[str] = mapped_column(Text)
    bear: Mapped[str] = mapped_column(Text)
    thesis: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    memo: Mapped["DDMemo"] = relationship(back_populates="versions")

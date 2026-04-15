"""사용자 계정, 관심종목, 알림, 피드백."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import Base, gen_id


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    byok_anthropic_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    byok_openai_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    watchlist_items: Mapped[list["WatchListItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WatchListItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="watchlist_items")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    channel_target: Mapped[str] = mapped_column(String(255))
    severity_threshold: Mapped[str] = mapped_column(String(10), default="med")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    alert_config_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("alert_configs.id"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DisclosureFeedback(Base):
    __tablename__ = "disclosure_feedback"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("users.id"), nullable=True, index=True
    )
    rcept_no: Mapped[str] = mapped_column(String(20), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MemoFeedback(Base):
    __tablename__ = "memo_feedback"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("users.id"), nullable=True, index=True
    )
    memo_version_id: Mapped[str] = mapped_column(String(12), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReferenceSummary(Base):
    """애널리스트 reference 요약 — fine-tuning 용 ground truth."""
    __tablename__ = "reference_summaries"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    rcept_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    summary_ko: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

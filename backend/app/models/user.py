"""사용자 계정, 관심종목, 알림, 피드백."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._base import Base, gen_id, utc_now


class Organization(Base):
    """Institutional workspace for shared analyst workflows."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class OrganizationMember(Base):
    """User membership and role inside an organization."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member_user"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    organization_id: Mapped[str] = mapped_column(String(12), ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class OrganizationInvite(Base):
    """Pending invitation into an organization."""

    __tablename__ = "organization_invites"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", "status", name="uq_org_invite_email_status"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    organization_id: Mapped[str] = mapped_column(String(12), ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(20), default="analyst")
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    invited_by_user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    accepted_by_user_id: Mapped[str | None] = mapped_column(String(12), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    default_organization_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("organizations.id"), nullable=True, index=True
    )
    byok_anthropic_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    byok_openai_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    watchlist_items: Mapped[list["WatchListItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WatchListItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="watchlist_items")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    channel_target: Mapped[str] = mapped_column(String(255))
    severity_threshold: Mapped[str] = mapped_column(String(10), default="med")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    alert_config_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("alert_configs.id"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DisclosureFeedback(Base):
    __tablename__ = "disclosure_feedback"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("users.id"), nullable=True, index=True
    )
    rcept_no: Mapped[str] = mapped_column(String(20), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MemoFeedback(Base):
    __tablename__ = "memo_feedback"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("users.id"), nullable=True, index=True
    )
    memo_version_id: Mapped[str] = mapped_column(String(12), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class EventReview(Base):
    """Analyst triage state for an anomalous disclosure event."""

    __tablename__ = "event_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "rcept_no", name="uq_event_review_user_event"),
        UniqueConstraint("organization_id", "rcept_no", name="uq_event_review_org_event"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("organizations.id"), nullable=True, index=True
    )
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("users.id"), nullable=True, index=True
    )
    rcept_no: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(16), default="reviewed")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AdminJobRun(Base):
    """Admin cron/job execution audit trail."""

    __tablename__ = "admin_job_runs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    job_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="running")
    triggered_by: Mapped[str] = mapped_column(String(40), default="admin_token")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    elapsed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class ReferenceSummary(Base):
    """애널리스트 reference 요약 — fine-tuning 용 ground truth."""
    __tablename__ = "reference_summaries"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    rcept_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    summary_ko: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ServerKeyUsage(Base):
    """BYOK 미설정 사용자가 서버 키로 호출한 일일 카운트.

    서버 관리자 쿼터 방어. kind: 'memo', 'ask' 분리.
    """
    __tablename__ = "server_key_usage"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD KST
    kind: Mapped[str] = mapped_column(String(20))  # memo / ask
    count: Mapped[int] = mapped_column(Integer, default=0)

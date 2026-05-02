"""공시/뉴스/실적 이벤트 — 시그널 소스."""
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, gen_id, utc_now


class Disclosure(Base):
    __tablename__ = "disclosures"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    rcept_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    corp_code: Mapped[str] = mapped_column(String(8), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    report_nm: Mapped[str] = mapped_column(String(200))
    rcept_dt: Mapped[str] = mapped_column(String(10), index=True)
    summary_ko: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    anomaly_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DisclosureEvidence(Base):
    """공시 판정/요약 근거.

    기관 PoC에서는 "왜 이 공시가 high/med인가"를 재현할 수 있어야 하므로
    원문 위치, 매칭 규칙, 모델 버전 같은 근거를 별도 append/update 가능한 레이어로 둔다.
    """
    __tablename__ = "disclosure_evidence"
    __table_args__ = (
        UniqueConstraint("rcept_no", "kind", name="uq_disclosure_evidence_kind"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    rcept_no: Mapped[str] = mapped_column(String(20), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    method: Mapped[str] = mapped_column(String(32))
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    quarter: Mapped[str] = mapped_column(String(8))
    scheduled_date: Mapped[str] = mapped_column(String(10), index=True)
    reported_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    op_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="dart")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    summary_ko: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarEvent(Base):
    """권리락/배당락/기준일/지급일 등 날짜 기반 이벤트.

    event_type: ex_right(권리락), last_with_right(권리부최종매매일),
                record_date(기준일), payment_date(지급일), listing_date(상장일)
    """
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("ticker", "event_type", "event_date", "rcept_no", name="uq_calendar_event"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    event_type: Mapped[str] = mapped_column(String(20), index=True)
    event_date: Mapped[str] = mapped_column(String(10), index=True)
    rcept_no: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

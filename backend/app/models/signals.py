"""공시/뉴스/실적 이벤트 — 시그널 소스."""
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, gen_id


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
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    summary_ko: Mapped[str | None] = mapped_column(Text, nullable=True)

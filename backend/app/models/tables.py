"""comad-stock 데이터 모델.

stock-strategy에서 재사용: User, WatchListItem, UserPreference, AlertConfig, AlertHistory, Portfolio, PortfolioHolding.
신규: Company, Disclosure, DDMemo, DDMemoVersion, NewsItem.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


# --- 재사용 모델 ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    byok_anthropic_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet 암호화
    byok_openai_key: Mapped[str | None] = mapped_column(Text, nullable=True)     # Fernet 암호화
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    watchlist_items: Mapped[list["WatchListItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WatchListItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)  # KRX 6자리
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="watchlist_items")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(12), ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # telegram, slack, discord
    channel_target: Mapped[str] = mapped_column(String(255))
    severity_threshold: Mapped[str] = mapped_column(String(10), default="med")  # low, med, high
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    alert_config_id: Mapped[str] = mapped_column(String(12), ForeignKey("alert_configs.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(30))  # disclosure_anomaly, memo_ready
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- 신규 모델 (DART 중심) ---

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # 6자리 종목코드
    corp_code: Mapped[str] = mapped_column(String(8), unique=True, index=True)  # DART 고유코드
    name_ko: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(50), nullable=True)
    market: Mapped[str] = mapped_column(String(20))  # KOSPI, KOSDAQ
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Disclosure(Base):
    __tablename__ = "disclosures"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    rcept_no: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # DART 접수번호
    corp_code: Mapped[str] = mapped_column(String(8), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    report_nm: Mapped[str] = mapped_column(String(200))
    rcept_dt: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    summary_ko: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI 요약
    anomaly_severity: Mapped[str | None] = mapped_column(String(10), nullable=True)  # low/med/high
    anomaly_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DDMemo(Base):
    __tablename__ = "dd_memos"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    user_id: Mapped[str | None] = mapped_column(String(12), ForeignKey("users.id"), nullable=True, index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    latest_version_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    versions: Mapped[list["DDMemoVersion"]] = relationship(
        back_populates="memo", cascade="all, delete-orphan", order_by="DDMemoVersion.version.desc()"
    )


class DDMemoVersion(Base):
    __tablename__ = "dd_memo_versions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    memo_id: Mapped[str] = mapped_column(String(12), ForeignKey("dd_memos.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    bull: Mapped[str] = mapped_column(Text)
    bear: Mapped[str] = mapped_column(Text)
    thesis: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text)  # JSON: [{type, url, rcept_no}]
    generated_by: Mapped[str] = mapped_column(String(50))  # 모델명
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memo: Mapped["DDMemo"] = relationship(back_populates="versions")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    summary_ko: Mapped[str | None] = mapped_column(Text, nullable=True)

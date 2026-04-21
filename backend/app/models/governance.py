"""지배구조 데이터 모델 — 최대주주(개인·법인), 임원, 기업간 지분.

Neo4j의 Person/Company 그래프와 병행 운용:
- SQL은 최근 스냅샷(대시보드 빠른 조회) + 소스 추적용 fact table
- Neo4j는 관계·순환출자·경로 질의용 인덱스

as_of 날짜로 시계열 스냅샷 적립. 가장 최근(as_of DESC) 1건이 현재값.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, gen_id


class MajorShareholder(Base):
    """특정증권등소유상황 / 대량보유 공시 파생 — 개인 또는 법인 주주."""

    __tablename__ = "major_shareholders"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "holder_name", "as_of", name="uq_major_shareholder_snapshot"
        ),
        Index("ix_major_shareholders_ticker_as_of", "ticker", "as_of"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    holder_name: Mapped[str] = mapped_column(String(120), index=True)
    # 'person' = 개인, 'corp' = 법인, 'fund' = 펀드/기관, 'special' = 특수관계
    holder_type: Mapped[str] = mapped_column(String(16))
    stake_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # holder가 법인이면 그 ticker (자기지분 제외) — 순환출자 검출용
    holder_ticker: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    as_of: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    source_rcept_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Insider(Base):
    """임원·주요주주 공시 파생 — 등기/미등기임원, 사외이사 등."""

    __tablename__ = "insiders"
    __table_args__ = (
        UniqueConstraint(
            "ticker", "person_name", "role", "as_of", name="uq_insider_snapshot"
        ),
        Index("ix_insiders_ticker_as_of", "ticker", "as_of"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    person_name: Mapped[str] = mapped_column(String(120))
    # '대표이사', '사외이사', '감사', '사내이사', '기타비상무이사', '감사위원' 등
    role: Mapped[str] = mapped_column(String(40))
    # 'exec' = 등기/미등기임원, 'outside' = 사외이사, 'audit' = 감사(위원)
    classification: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_registered: Mapped[bool | None] = mapped_column(nullable=True)  # 등기 여부
    own_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    as_of: Mapped[str] = mapped_column(String(10), index=True)
    source_rcept_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GovernanceExtractRequest(Base):
    """사용자가 트리거한 지배구조 추출 요청 로그.

    용도:
    1. 쿨다운: 같은 ticker를 1시간 내 중복 트리거 방지 (Anthropic 비용 보호)
    2. Rate limit: 같은 IP가 시간당 과도 호출 방지
    3. 상태 노출: 처리 중/완료/실패 프런트 상태 표시

    Why not 큐 테이블: 추출이 20-60s 동기 호출로 충분해 별도 worker가 불필요.
    이 테이블은 rate limit + 감사 로그 목적. 나중에 async 워커가 필요해지면
    status='pending' 행을 별도 잡이 폴링하도록 확장 가능.
    """

    __tablename__ = "governance_extract_requests"
    __table_args__ = (
        Index("ix_gov_extract_ticker_at", "ticker", "requested_at"),
        Index("ix_gov_extract_ip_at", "requester_ip", "requested_at"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    ticker: Mapped[str] = mapped_column(String(10))
    # 'processing' → extract 진행 중, 'done' → 성공, 'no_data' → governance 공시 없음,
    # 'failed' → 예외 발생, 'cooldown'/'ip_limit' → 실행 없이 거절됨
    status: Mapped[str] = mapped_column(String(16))
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requester_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 추출 결과 요약 (persons 수, corps 수) — 간단한 문자열
    result_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)


class CorporateOwnership(Base):
    """기업간 지분 보유 — Company → Company edge. 순환출자 검출 1차 소스.

    Neo4j에도 (:Company)-[:HOLDS_SHARES]->(:Company) 로 동기화.
    """

    __tablename__ = "corporate_ownership"
    __table_args__ = (
        UniqueConstraint(
            "parent_ticker", "child_ticker", "as_of",
            name="uq_corp_ownership_snapshot",
        ),
        Index("ix_corp_ownership_child", "child_ticker", "as_of"),
        Index("ix_corp_ownership_parent", "parent_ticker", "as_of"),
    )

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=gen_id)
    parent_ticker: Mapped[str] = mapped_column(String(10), index=True)
    child_ticker: Mapped[str] = mapped_column(String(10), index=True)
    parent_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    child_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stake_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    as_of: Mapped[str] = mapped_column(String(10), index=True)
    source_rcept_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

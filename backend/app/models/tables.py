"""Backward-compat facade.

기존 `from app.models.tables import X` 임포트를 깨지 않기 위한 re-export.
실제 정의는 `_base`, `user`, `market`, `signals`, `memo` 모듈에 분산.
"""
from app.models._base import Base, gen_id
from app.models.user import (
    AlertConfig,
    AlertHistory,
    AdminJobRun,
    DisclosureFeedback,
    EventReview,
    MemoFeedback,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    ReferenceSummary,
    ServerKeyUsage,
    User,
    WatchListItem,
)
from app.models.market import Company, FinancialSnapshot, ShortSellingSnapshot
from app.models.signals import CalendarEvent, Disclosure, DisclosureEvidence, EarningsEvent, NewsItem
from app.models.memo import DDMemo, DDMemoVersion
from app.models.governance import (
    CorporateOwnership,
    GovernanceExtractRequest,
    Insider,
    MajorShareholder,
)

__all__ = [
    "Base",
    "gen_id",
    "User",
    "WatchListItem",
    "AlertConfig",
    "AlertHistory",
    "AdminJobRun",
    "DisclosureFeedback",
    "EventReview",
    "MemoFeedback",
    "Organization",
    "OrganizationInvite",
    "OrganizationMember",
    "ReferenceSummary",
    "ServerKeyUsage",
    "Company",
    "FinancialSnapshot",
    "ShortSellingSnapshot",
    "Disclosure",
    "DisclosureEvidence",
    "EarningsEvent",
    "NewsItem",
    "CalendarEvent",
    "DDMemo",
    "DDMemoVersion",
    "MajorShareholder",
    "Insider",
    "CorporateOwnership",
    "GovernanceExtractRequest",
]

"""전체 수집 오케스트레이터. stock-strategy 패턴 계승.

순서: DART → KRX → 뉴스.
"""
import logging

from app.services.collectors import dart, krx, news
from app.services.anomaly import detector
from app.services.retry import with_retry

logger = logging.getLogger(__name__)


async def collect_all() -> dict:
    """DART → KRX → News → anomaly. 각 단계 3회 재시도(exp backoff)."""
    stages = [
        ("dart", dart.fetch_recent_disclosures),
        ("krx", krx.fetch_kospi_quotes),
        ("news", news.fetch_news),
        ("anomaly", detector.scan_new_disclosures),
    ]
    result: dict = {}
    for name, fn in stages:
        outcome = await with_retry(fn, attempts=3, name=name)
        if isinstance(outcome, Exception):
            result[name] = {"error": str(outcome)}
        else:
            result[name] = outcome
    return result

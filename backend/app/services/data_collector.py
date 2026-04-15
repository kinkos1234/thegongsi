"""전체 수집 오케스트레이터. stock-strategy 패턴 계승.

순서: DART → KRX → 뉴스.
"""
import logging

from app.services.collectors import dart, krx, news
from app.services.anomaly import detector

logger = logging.getLogger(__name__)


async def collect_all() -> dict:
    result = {}
    try:
        result["dart"] = await dart.fetch_recent_disclosures()
    except Exception as e:
        logger.exception("DART 수집 실패")
        result["dart"] = {"error": str(e)}

    try:
        result["krx"] = await krx.fetch_kospi_quotes()
    except Exception as e:
        logger.exception("KRX 수집 실패")
        result["krx"] = {"error": str(e)}

    try:
        result["news"] = await news.fetch_news()
    except Exception as e:
        logger.exception("뉴스 수집 실패")
        result["news"] = {"error": str(e)}

    # 신규 공시에 대해 이상징후 스캔 (규칙+LLM)
    try:
        result["anomaly"] = await detector.scan_new_disclosures()
    except Exception as e:
        logger.exception("이상징후 스캔 실패")
        result["anomaly"] = {"error": str(e)}

    return result

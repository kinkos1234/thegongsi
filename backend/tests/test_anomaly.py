"""anomaly detector 규칙 기반 판정 테스트."""
from app.services.anomaly.detector import rule_based_severity


def test_high_keyword_delisting():
    sev, reason = rule_based_severity("주권상장폐지결정")
    assert sev == "high"
    assert "상장폐지" in reason


def test_high_keyword_audit():
    sev, _ = rule_based_severity("외부감사인의 감사의견거절")
    assert sev == "high"


def test_med_keyword_shareholder():
    sev, _ = rule_based_severity("최대주주변경 공시")
    assert sev == "med"


def test_no_match():
    sev, reason = rule_based_severity("분기보고서 2026 1Q")
    assert sev is None
    assert reason is None

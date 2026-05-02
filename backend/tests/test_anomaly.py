"""anomaly detector 규칙 기반 판정 테스트."""
import pytest

from app.database import async_session
from app.models.tables import Company, Disclosure, DisclosureEvidence
from app.services.anomaly.detector import (
    backfill_missing_evidence,
    rule_based_match,
    rule_based_severity,
    scan_new_disclosures,
)


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


def test_rule_based_match_returns_audit_evidence():
    sev, reason, evidence = rule_based_match("주요사항보고서(유상증자결정)")

    assert sev == "high"
    assert "유상증자결정" in reason
    assert evidence["keyword"] == "유상증자결정"
    assert evidence["source"] == "report_nm"


@pytest.mark.asyncio
async def test_scan_new_disclosures_persists_severity_evidence(monkeypatch, client):
    monkeypatch.setattr("app.services.anomaly.detector.settings.anthropic_api_key", "", raising=False)
    async with async_session() as db:
        db.add(Company(ticker="005930", corp_code="00126380", name_ko="삼성전자", market="KOSPI"))
        db.add(
            Disclosure(
                rcept_no="20260430001234",
                corp_code="00126380",
                ticker="005930",
                report_nm="주요사항보고서(유상증자결정)",
                rcept_dt="2026-04-30",
            )
        )
        await db.commit()

    result = await scan_new_disclosures()

    assert result["scanned"] == 1
    assert result["flagged"] == 1

    async with async_session() as db:
        rows = (await db.execute(
            DisclosureEvidence.__table__.select().where(
                DisclosureEvidence.rcept_no == "20260430001234"
            )
        )).all()
    assert len(rows) == 1

    r = await client.get("/api/disclosures/20260430001234/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["evidence"][0]["kind"] == "severity"
    assert body["evidence"][0]["method"] == "rule"
    assert body["evidence"][0]["items"][0]["keyword"] == "유상증자결정"


@pytest.mark.asyncio
async def test_backfill_missing_evidence_for_legacy_disclosures(client):
    async with async_session() as db:
        db.add(Company(ticker="000660", corp_code="00164779", name_ko="SK하이닉스", market="KOSPI"))
        db.add(
            Disclosure(
                rcept_no="20260430004321",
                corp_code="00164779",
                ticker="000660",
                report_nm="분기보고서 2026 1Q",
                rcept_dt="2026-04-30",
                anomaly_severity="low",
                anomaly_reason="규칙 매칭 없음",
            )
        )
        await db.commit()

    result = await backfill_missing_evidence(limit=100)

    assert result["backfilled"] == 1
    r = await client.get("/api/disclosures/20260430004321/evidence")
    assert r.status_code == 200
    item = r.json()["evidence"][0]["items"][0]
    assert r.json()["evidence"][0]["method"] == "rule_backfill"
    assert item["matched"] is False
    assert item["source"] == "report_nm"

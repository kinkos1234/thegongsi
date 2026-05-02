import json

import pytest

from app.database import async_session
from app.models.tables import AdminJobRun, Company, DDMemo, DDMemoVersion, Disclosure, DisclosureEvidence


@pytest.mark.asyncio
async def test_readiness_returns_quality_snapshot(client):
    async with async_session() as db:
        db.add(Company(ticker="005930", corp_code="00126380", name_ko="삼성전자", market="KOSPI"))
        db.add(
            Disclosure(
                rcept_no="20260430000001",
                corp_code="00126380",
                ticker="005930",
                report_nm="주요사항보고서",
                rcept_dt="2026-04-30",
                anomaly_severity="high",
            )
        )
        db.add(
            DisclosureEvidence(
                rcept_no="20260430000001",
                kind="severity",
                method="rule",
                evidence_json=json.dumps([{"type": "keyword_match"}]),
            )
        )
        db.add(AdminJobRun(job_id="daily_collection", status="success", result_json="{}"))
        await db.commit()

    r = await client.get("/api/stats/readiness")

    assert r.status_code == 200
    body = r.json()
    assert body["coverage"]["companies"] == 1
    assert body["coverage"]["disclosures"] == 1
    assert body["coverage"]["anomalies_7d"] >= 0
    assert body["disclosure_evidence"]["with_severity_evidence_7d"] == 1
    assert body["operations"]["admin_runs_24h"] == 1
    assert {c["id"] for c in body["checks"]} >= {
        "fresh_disclosures",
        "severity_evidence",
        "memo_evidence",
        "admin_job_audit",
    }


@pytest.mark.asyncio
async def test_latest_memo_exposes_evidence_metadata(client):
    async with async_session() as db:
        memo = DDMemo(ticker="005930", user_id=None)
        db.add(memo)
        await db.flush()
        version = DDMemoVersion(
            memo_id=memo.id,
            version=1,
            bull="bull [출처: rcept_no=20260430000001]",
            bear="bear",
            thesis="thesis",
            sources=json.dumps(
                [{"type": "disclosure", "rcept_no": "20260430000001"}],
                ensure_ascii=False,
            ),
            generated_by="claude-sonnet-4-6|key=server|warn=none",
        )
        db.add(version)
        await db.flush()
        memo.latest_version_id = version.id
        await db.commit()

    r = await client.get("/api/memos/005930")

    assert r.status_code == 200
    body = r.json()
    assert body["generated_by"].startswith("claude-sonnet")
    assert body["sources"]["disclosures"][0]["rcept_no"] == "20260430000001"


@pytest.mark.asyncio
async def test_event_inbox_packages_anomalies_for_review(client):
    async with async_session() as db:
        db.add(Company(ticker="000660", corp_code="00164779", name_ko="SK하이닉스", market="KOSPI", sector="반도체"))
        db.add(
            Disclosure(
                rcept_no="20260430000002",
                corp_code="00164779",
                ticker="000660",
                report_nm="주요사항보고서(유상증자결정)",
                rcept_dt="2026-04-30",
                anomaly_severity="med",
                anomaly_reason="자금조달 이벤트",
                raw_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260430000002",
            )
        )
        await db.commit()

    r = await client.get("/api/stats/event-inbox?days=7&limit=10")

    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["new"] == 1
    assert body["items"][0]["status"] == "new"
    assert body["items"][0]["actions"] == ["review", "dismiss", "escalate"]
    assert body["items"][0]["evidence"]["rcept_no"] == "20260430000002"


@pytest.mark.asyncio
async def test_data_quality_drilldown_lists_actionable_issues(client):
    async with async_session() as db:
        db.add(Company(ticker="111111", corp_code="11111111", name_ko="중복회사", market="KOSPI"))
        db.add(Company(ticker="222222", corp_code="22222222", name_ko="중복회사", market="KOSDAQ"))
        db.add(
            Disclosure(
                rcept_no="20260430000003",
                corp_code="11111111",
                ticker="111111",
                report_nm="분기보고서",
                rcept_dt="2026-04-30",
                anomaly_severity=None,
                summary_ko=None,
            )
        )
        db.add(
            Disclosure(
                rcept_no="20260430000004",
                corp_code="22222222",
                ticker="222222",
                report_nm="주요사항보고서(유상증자결정)",
                rcept_dt="2026-04-30",
                anomaly_severity="high",
                summary_ko="요약",
            )
        )
        db.add(AdminJobRun(job_id="daily_collection", status="failed", error="DART timeout"))
        await db.commit()

    r = await client.get("/api/stats/data-quality?days=7&limit=10")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "warn"
    assert body["counts"]["unclassified_disclosures"] == 1
    assert body["counts"]["missing_summaries"] == 1
    assert body["counts"]["missing_severity_evidence"] == 1
    assert body["counts"]["duplicate_company_names"] == 1
    assert body["issues"]["failed_admin_jobs"][0]["error"] == "DART timeout"

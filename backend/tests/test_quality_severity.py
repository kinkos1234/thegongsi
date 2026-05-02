import pytest

from app.database import async_session
from app.models.tables import Company, Disclosure
from app.services.quality.severity_eval import evaluate_cases, evaluate_default_gold, load_gold_cases
from app.services.quality.severity_sampling import build_labeling_sample


def test_severity_gold_set_loads():
    cases = load_gold_cases()

    assert len(cases) >= 10
    assert {case["expected"] for case in cases} >= {"high", "med", "low"}


def test_severity_eval_reports_confusion_and_error_sets():
    report = evaluate_cases([
        {"id": "tp", "report_nm": "주권상장폐지결정", "expected": "high"},
        {"id": "fn", "report_nm": "최대주주변경", "expected": "high"},
        {"id": "fp", "report_nm": "주요사항보고서", "expected": "low"},
    ])

    assert report["total"] == 3
    assert report["passed"] == 1
    assert report["confusion"]["high"]["high"] == 1
    assert report["confusion"]["high"]["med"] == 1
    assert report["confusion"]["low"]["med"] == 1
    assert report["labels"]["high"]["recall"] == 0.5
    assert len(report["false_positives"]) == 1


def test_default_severity_eval_has_minimum_quality_bar():
    report = evaluate_default_gold()

    assert report["status"] == "pass"
    assert report["accuracy"] >= 0.75
    assert report["labels"]["high"]["recall"] >= 0.8
    assert report["total"] >= 10


@pytest.mark.asyncio
async def test_severity_quality_api(client):
    r = await client.get("/api/stats/quality/severity")

    assert r.status_code == 200
    body = r.json()
    assert body["suite"] == "severity_gold_v1"
    assert body["total"] >= 10
    assert "confusion" in body
    assert "thresholds" in body


@pytest.mark.asyncio
async def test_severity_quality_admin_job(client, monkeypatch):
    monkeypatch.setattr("app.routers.admin_jobs.settings.admin_jobs_token", "test-admin-token", raising=False)

    r = await client.post(
        "/api/admin/jobs/quality_severity_eval",
        headers={"X-Admin-Token": "test-admin-token"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["job"] == "quality_severity_eval"
    assert body["result"]["suite"] == "severity_gold_v1"


@pytest.mark.asyncio
async def test_severity_labeling_sample_is_stratified(client):
    async with async_session() as db:
        db.add(Company(ticker="111111", corp_code="11111111", name_ko="샘플하이", market="KOSPI"))
        db.add(Company(ticker="222222", corp_code="22222222", name_ko="샘플미드", market="KOSPI"))
        db.add(Company(ticker="333333", corp_code="33333333", name_ko="샘플로우", market="KOSPI"))
        db.add(Disclosure(
            rcept_no="20260502010001",
            corp_code="11111111",
            ticker="111111",
            report_nm="주요사항보고서(유상증자결정)",
            rcept_dt="2026-05-02",
        ))
        db.add(Disclosure(
            rcept_no="20260502010002",
            corp_code="22222222",
            ticker="222222",
            report_nm="최대주주변경",
            rcept_dt="2026-05-02",
        ))
        db.add(Disclosure(
            rcept_no="20260502010003",
            corp_code="33333333",
            ticker="333333",
            report_nm="분기보고서 2026.03",
            rcept_dt="2026-05-02",
        ))
        await db.commit()

    async with async_session() as db:
        sample = await build_labeling_sample(db, days=7, per_label=1)

    assert sample["counts"] == {"high": 1, "med": 1, "low": 1}
    assert {item["predicted"] for item in sample["items"]} == {"high", "med", "low"}

    r = await client.get("/api/stats/quality/severity/sample?days=7&per_label=1")
    assert r.status_code == 200
    assert r.json()["counts"]["high"] == 1

    r = await client.get("/api/stats/quality/severity/sample.csv?days=7&per_label=1")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "label,label_note,predicted" in r.text
    assert "20260502010001" in r.text

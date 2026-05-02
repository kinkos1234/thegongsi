import pytest
from sqlalchemy import select

from app.database import async_session
from app.models.tables import AdminJobRun


@pytest.mark.asyncio
async def test_admin_job_run_is_audited(client, monkeypatch):
    monkeypatch.setattr("app.routers.admin_jobs.settings.admin_jobs_token", "test-admin-token", raising=False)
    headers = {"X-Admin-Token": "test-admin-token"}

    r = await client.post("/api/admin/jobs/backfill_disclosure_evidence?max_new=10", headers=headers)

    assert r.status_code == 200
    body = r.json()
    assert body["job"] == "backfill_disclosure_evidence"
    assert body["run_id"]

    async with async_session() as db:
        run = await db.get(AdminJobRun, body["run_id"])
    assert run is not None
    assert run.status == "success"
    assert run.job_id == "backfill_disclosure_evidence"
    assert '"max_new": 10' in run.params_json

    r = await client.get("/api/admin/jobs/runs", headers=headers)
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert runs[0]["id"] == body["run_id"]
    assert runs[0]["status"] == "success"


@pytest.mark.asyncio
async def test_admin_job_validation_failure_is_audited(client, monkeypatch):
    monkeypatch.setattr("app.routers.admin_jobs.settings.admin_jobs_token", "test-admin-token", raising=False)
    headers = {"X-Admin-Token": "test-admin-token"}

    r = await client.post("/api/admin/jobs/extract_governance_ticker", headers=headers)

    assert r.status_code == 400
    async with async_session() as db:
        rows = (
            await db.execute(select(AdminJobRun).where(AdminJobRun.job_id == "extract_governance_ticker"))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "failed"

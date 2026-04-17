"""외부 cron(GitHub Actions)이 트리거하는 관리자 작업 엔드포인트.

Why: Fly의 `min_machines_running=0` + 스케줄러가 FastAPI 프로세스 외부에 있어서
`scripts/scheduler.py`를 프로덕션에서 띄울 방법이 없음. GitHub Actions cron이
각 시각에 여기 POST해서 백그라운드 서브프로세스로 실제 job을 실행시킴.
Actions는 2xx 받으면 완료로 간주하고, job의 실제 stdout/stderr는 Fly logs에 남음.

보안: `X-Admin-Token` 헤더가 `settings.admin_jobs_token`과 일치해야 실행.
토큰 미설정이면 503 (프로덕션 실수 방지).
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# job_id → (argv, description). "inline" job은 특별 처리.
JOBS: dict[str, tuple[list[str] | str, str]] = {
    "daily_collection": ("inline", "DART/KRX 일일 수집 + 알림 체크"),
    "weekly_index_sync": (
        ["scripts/weekly_sync.py"],
        "KOSPI 200 + KOSDAQ 150 구성원 sync + backfill",
    ),
    "weekly_market_refresh_seed": (
        ["scripts/seed_dart_native.py"],
        "상장사 신규 등록 (weekly_market_refresh part 1)",
    ),
    "weekly_market_refresh_enrich": (
        ["scripts/enrich_market.py"],
        "KIND KOSPI/KOSDAQ 라벨 재적용 (weekly_market_refresh part 2)",
    ),
    "daily_dividend_scan": (
        ["scripts/scan_dividend_dates.py", "--days", "14"],
        "배당 ex-date 증분 스캔",
    ),
    "daily_ex_dates_scan": (
        ["scripts/scan_ex_dates_v2.py", "--days", "14"],
        "유/무상증자 권리락 증분 스캔",
    ),
    "daily_earnings_scan": (
        ["scripts/scan_earnings.py", "--days", "14"],
        "잠정/확정실적 공정공시 수집",
    ),
    "weekly_db_backup": (
        ["scripts/db_backup.py", "--out", "/tmp/backups"],
        "13 테이블 JSONL 백업",
    ),
}


def _require_token(x_admin_token: str | None) -> None:
    token = settings.admin_jobs_token
    if not token:
        # 프로덕션에서 실수로 토큰 미설정 시 누구나 cron을 칠 수 있으면 안 됨.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_JOBS_TOKEN not configured on server",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


def _run_subprocess(argv_tail: list[str], job_id: str) -> None:
    """Background task: scripts/xxx.py 를 backend/ CWD에서 실행하고 로그로 남김."""
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cmd = [sys.executable, *argv_tail]
    t0 = datetime.now(timezone.utc)
    logger.info("admin_job %s start cmd=%s cwd=%s", job_id, " ".join(cmd), cwd)
    try:
        # 15분 상한 — daily_earnings_scan이 제일 오래 걸림(2-3분 예상). 여유 ×5.
        proc = subprocess.run(
            cmd, cwd=cwd, env=os.environ.copy(),
            capture_output=True, text=True, timeout=900, check=False,
        )
        dt = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.info(
            "admin_job %s done rc=%s elapsed=%.1fs stdout_tail=%r stderr_tail=%r",
            job_id, proc.returncode, dt,
            (proc.stdout or "")[-500:], (proc.stderr or "")[-500:],
        )
    except subprocess.TimeoutExpired:
        dt = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.error("admin_job %s TIMEOUT after %.0fs", job_id, dt)
    except Exception:
        logger.exception("admin_job %s crashed", job_id)


async def _run_daily_collection() -> None:
    """Inline: scripts/scheduler.py:run_once(check_alerts=True) 와 동일."""
    from app.database import async_session
    from app.services.alert_service import check_and_alert
    from app.services.data_collector import collect_all

    t0 = datetime.now(timezone.utc)
    try:
        r = await collect_all()
        logger.info("daily_collection collect_all: %s", r)
    except Exception:
        logger.exception("daily_collection collect_all failed")
    async with async_session() as db:
        try:
            alert = await check_and_alert(db)
            logger.info("daily_collection alerts: %s", alert)
        except Exception:
            logger.exception("daily_collection check_and_alert failed")
    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    logger.info("daily_collection done elapsed=%.1fs", dt)


@router.get("/")
async def list_jobs(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    """사용 가능한 job 목록 (디버깅용). 토큰 없으면 401/503."""
    _require_token(x_admin_token)
    return {jid: desc for jid, (_, desc) in JOBS.items()}


@router.post("/{job_id}")
async def trigger_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Job을 백그라운드에서 실행시키고 즉시 202를 반환.

    실제 완료/실패 결과는 서버 로그(Fly logs)에서 확인. Actions 관점에선
    HTTP 202 = "트리거 성공" 으로 충분. (워커 풀이 작아서 오래 블록시키면
    다른 API가 막힘.)
    """
    _require_token(x_admin_token)
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")

    argv, desc = JOBS[job_id]
    if argv == "inline" and job_id == "daily_collection":
        background_tasks.add_task(asyncio.create_task, _run_daily_collection())  # type: ignore[arg-type]
    else:
        assert isinstance(argv, list)
        background_tasks.add_task(_run_subprocess, argv, job_id)

    return {
        "job": job_id,
        "description": desc,
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted",
    }

"""외부 cron(GitHub Actions)이 트리거하는 관리자 작업 엔드포인트.

Why: Fly의 `min_machines_running=0` + 스케줄러가 FastAPI 프로세스 외부에 있어서
`scripts/scheduler.py`를 프로덕션에서 띄울 방법이 없음. GitHub Actions cron이
각 시각에 여기 POST해서 서브프로세스로 실제 job을 실행시킴.

**동기 응답 모델 (2026-04-18 수정)**: 이전 BackgroundTasks 버전은 subprocess가
돌고 있는 동안 Fly가 HTTP 요청을 이미 끝난 것으로 보고 머신을 auto-stop시켜
subprocess를 죽이는 버그가 있었음. 지금은 subprocess 완료까지 HTTP 응답을
대기시켜 머신을 깨어 있게 유지. Actions는 6h timeout이라 문제없음.

보안: `X-Admin-Token` 헤더가 `settings.admin_jobs_token`과 일치해야 실행.
토큰 미설정이면 503 (프로덕션 실수 방지).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# URL query-string 안의 키·토큰 값을 REDACTED로 치환. stdout/stderr tail을
# Actions 응답 바디에 넣기 전에 반드시 통과시킨다 — public repo의 Actions
# 로그는 누구나 볼 수 있으므로 평문 키가 노출되면 즉시 rotation 대상.
_SECRET_QS_RE = re.compile(
    r'(?P<sep>[?&]|\b)(?P<name>crtfc_key|api_key|apikey|token|auth|password|secret|key)=[^&\s"\'<>]+',
    re.IGNORECASE,
)
# DART API key는 40-char hex (기본 포맷). URL query 바깥에서 문자열 단독으로
# 나타날 수도 있음 — 보수적으로 hex 40자 시퀀스를 마스킹.
_HEX40_RE = re.compile(r'\b[a-fA-F0-9]{40}\b')


def _mask_secrets(text: str | None) -> str:
    if not text:
        return text or ""
    redacted = _SECRET_QS_RE.sub(r'\g<sep>\g<name>=REDACTED', text)
    redacted = _HEX40_RE.sub("REDACTED_HEX40", redacted)
    return redacted

router = APIRouter()


# job_id → (argv, description). "inline" job은 특별 처리.
JOBS: dict[str, tuple[list[str] | str, str]] = {
    "graph_ping": ("inline", "Neo4j 가벼운 Cypher 핑 (AuraDB idle-hibernate 방지)"),
    "seed_supply_chains": (["scripts/seed_supply_chains.py"], "공급망 seed YAML → Neo4j SUPPLIES 엣지 upsert"),
    "extract_supply_chains": ("inline", "최근 공시에서 공급 관계 LLM 추출 → Neo4j SUPPLIES upsert"),
    "daily_collection": ("inline", "DART/KRX 일일 수집 + 알림 체크"),
    "historical_backfill": (
        "inline",
        "과거 N일 DART 공시 일회성 backfill + anomaly scan (gap 채우기, 기본 30일, ?days=7-90)",
    ),
    "backfill_year_gaps": (
        "inline",
        "DART day-by-day 역순 순회로 2026 gap 채움 (기본 150/호출, start=2026-01-01, ?max_new=N&start=YYYY-MM-DD&cursor=YYYY-MM-DD)",
    ),
    "scan_anomalies_bulk": (
        "inline",
        "severity=NULL 공시 일괄 스캔 (rule + LLM). 빈 배치 나올 때까지 반복, 최대 50회.",
    ),
    "sync_disclosures_all": (
        "inline",
        "DB 전체 Disclosure → Neo4j sync (페이지네이션, MERGE 멱등)",
    ),
    "backfill_watchlist_governance": (
        "inline",
        "전체 watchlist 종목 governance 스냅샷 일괄 추출 (기존 누락 backfill)",
    ),
    "extract_governance_ticker": (
        "inline",
        "단일 ticker governance 추출 (콜드 종목 긴급 채움용, ?ticker=XXXXXX)",
    ),
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


def _run_subprocess_sync(argv_tail: list[str], job_id: str) -> dict:
    """scripts/xxx.py 를 backend/ CWD에서 실행하고 결과 dict 반환. 호출자가 await."""
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
        stdout_tail = _mask_secrets((proc.stdout or "")[-500:])
        stderr_tail = _mask_secrets((proc.stderr or "")[-500:])
        logger.info(
            "admin_job %s done rc=%s elapsed=%.1fs stdout_tail=%r stderr_tail=%r",
            job_id, proc.returncode, dt, stdout_tail, stderr_tail,
        )
        return {
            "rc": proc.returncode,
            "elapsed_seconds": round(dt, 1),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
    except subprocess.TimeoutExpired:
        dt = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.error("admin_job %s TIMEOUT after %.0fs", job_id, dt)
        return {"rc": -1, "elapsed_seconds": round(dt, 1), "error": "timeout"}
    except Exception as e:
        logger.exception("admin_job %s crashed", job_id)
        return {"rc": -2, "error": f"{type(e).__name__}: {e}"}


async def _run_graph_ping() -> dict:
    """AuraDB Free 는 idle 72h 후 hibernate → 첫 쿼리 30-60s 콜드 스타트.
    이 job 을 6h 주기로 돌려 hibernate 를 예방."""
    t0 = datetime.now(timezone.utc)
    try:
        from app.services.graph.client import session
        async with session(read_only=True) as s:
            r = await s.run("RETURN 1 AS one")
            record = await r.single()
            one = record["one"] if record else None
        dt = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.info("graph_ping ok elapsed=%.2fs one=%s", dt, one)
        return {"ok": True, "elapsed_seconds": round(dt, 2), "one": one}
    except Exception as e:
        dt = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.exception("graph_ping failed after %.2fs", dt)
        return {"ok": False, "elapsed_seconds": round(dt, 2), "error": f"{type(e).__name__}: {e}"}


async def _run_backfill_watchlist_governance(backfill_days: int = 0) -> dict:
    """전체 watchlist 의 distinct ticker 에 대해 governance extractor 를 돌려
    major_shareholders / insiders / corporate_ownership 테이블을 채우고
    Neo4j HOLDS / HOLDS_SHARES 엣지를 생성한다.

    - 사용자 간 중복 ticker 는 단 한 번만 처리 (Anthropic 요청 절감).
    - backfill_days > 0 이면 각 ticker 당 `backfill_ticker(days=backfill_days)` 를
      선행 실행 — 사업/반기/분기보고서가 90일 윈도우 밖이라 누락되던 케이스 커버.
    - ticker 간 0.5s 간격으로 rate-limit 보호.
    """
    import asyncio as _asyncio

    from sqlalchemy import select as _select

    from app.database import async_session
    from app.models.tables import WatchListItem
    from app.services.collectors.dart import backfill_ticker
    from app.services.graph.extractor import extract_from_disclosures

    t0 = datetime.now(timezone.utc)
    async with async_session() as db:
        res = await db.execute(_select(WatchListItem.ticker).distinct())
        tickers = sorted({t for (t,) in res.all() if t})

    results: list[dict] = []
    ok = 0
    empty = 0
    errors = 0
    for t in tickers:
        backfill_info: dict | None = None
        if backfill_days > 0:
            try:
                backfill_info = await backfill_ticker(t, days=backfill_days)
            except Exception as e:
                backfill_info = {"status": "error", "error": f"{type(e).__name__}: {e}"}
                logger.warning("backfill_ticker %s failed: %s", t, e)
        try:
            r = await extract_from_disclosures(t)
        except Exception as e:
            r = {"status": "error", "ticker": t, "error": f"{type(e).__name__}: {e}"}
            errors += 1
            logger.warning("watchlist_governance %s failed: %s", t, e)
        else:
            status = r.get("status")
            if status == "ok":
                ok += 1
            elif status == "no_governance_disclosures":
                empty += 1
            else:
                errors += 1
        entry = {"ticker": t, **{k: v for k, v in r.items() if k != "ticker"}}
        if backfill_info is not None:
            entry["backfill"] = backfill_info
        results.append(entry)
        await _asyncio.sleep(0.5)

    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    return {
        "elapsed_seconds": round(dt, 1),
        "total_tickers": len(tickers),
        "backfill_days": backfill_days,
        "ok": ok,
        "empty": empty,
        "errors": errors,
        "per_ticker": results,
    }


async def _run_scan_anomalies_bulk(max_iterations: int = 50) -> dict:
    """severity 미판정(NULL) 공시를 일괄 스캔. `scan_new_disclosures()`를
    빈 배치가 나올 때까지 반복 호출 — 각 배치 limit 1000, 총 max_iterations 회 상한.

    Why: backfill_year_gaps 로 대량 공시가 들어오면 anomaly_severity=NULL
    상태로 쌓여 프론트 severity 필터에 잡히지 않음. 이 잡으로 일괄 처리.
    """
    from app.services.anomaly.detector import scan_new_disclosures

    t0 = datetime.now(timezone.utc)
    total_scanned = 0
    total_flagged = 0
    iterations = 0
    for _ in range(max_iterations):
        res = await scan_new_disclosures()
        iterations += 1
        s = res.get("scanned", 0)
        f = res.get("flagged", 0)
        total_scanned += s
        total_flagged += f
        if s == 0:
            break

    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    return {
        "iterations": iterations,
        "scanned": total_scanned,
        "flagged": total_flagged,
        "stopped_at_cap": iterations >= max_iterations and s > 0,
        "elapsed_seconds": round(elapsed, 1),
    }


async def _run_backfill_year_gaps(
    start: str = "2026-01-01",
    max_new: int = 150,
    cursor: str | None = None,
) -> dict:
    """DART list.json을 day-by-day 역순 순회하며 DB 누락분만 주입.

    Why: 3개월 bulk fetch는 max_rows(15K)에 묶이고 Fly 512MB에서 OOM 위험.
    날짜별 1회 호출 + 페이지별 증분 commit → 메모리 상수, 멱등 (rcept_no UNIQUE).

    cursor가 있으면 해당 날짜부터 재개, 없으면 KST 오늘부터. max_new 도달 또는
    `start` 이전으로 내려가면 종료 (done=True 시 다음 호출 불필요).
    """
    from app.services.collectors.dart import KST, _fetch_list
    from app.database import async_session
    from app.models.signals import Disclosure
    from sqlalchemy import select
    from datetime import date as _date, datetime as _dt, timedelta as _td

    def _parse_iso(s: str) -> _date:
        return _dt.strptime(s, "%Y-%m-%d").date()

    stop_date = _parse_iso(start)
    today_kst = _dt.now(KST).date()
    cursor_date = _parse_iso(cursor) if cursor else today_kst

    t0 = datetime.now(timezone.utc)
    inserted = 0
    skipped_dup = 0
    skipped_noticker = 0
    days_walked = 0

    day = cursor_date
    loop = asyncio.get_event_loop()
    while day >= stop_date and (max_new <= 0 or inserted < max_new):
        ymd = day.strftime("%Y%m%d")
        try:
            rows = await loop.run_in_executor(
                None,
                lambda d=ymd: _fetch_list(
                    bgn_de=d, end_de=d, max_rows=1000, last_reprt_at="Y"
                ),
            )
        except Exception as e:
            logger.warning("backfill_year_gaps fetch %s failed: %s", ymd, e)
            rows = []

        async with async_session() as db:
            for row in rows:
                if not row["ticker"]:
                    skipped_noticker += 1
                    continue
                existing = await db.execute(
                    select(Disclosure).where(Disclosure.rcept_no == row["rcept_no"])
                )
                if existing.scalar_one_or_none():
                    skipped_dup += 1
                    continue
                db.add(Disclosure(**row))
                inserted += 1
                if max_new > 0 and inserted >= max_new:
                    break
            await db.commit()

        days_walked += 1
        if max_new > 0 and inserted >= max_new:
            break
        day = day - _td(days=1)

    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    done = day < stop_date
    return {
        "inserted": inserted,
        "skipped_duplicate": skipped_dup,
        "skipped_no_ticker": skipped_noticker,
        "days_walked": days_walked,
        "cursor_start": cursor_date.strftime("%Y-%m-%d"),
        "cursor_end": day.strftime("%Y-%m-%d"),
        "next_cursor": None if done else day.strftime("%Y-%m-%d"),
        "stop_date": start,
        "elapsed_seconds": round(elapsed, 1),
        "done": done,
    }


async def _run_historical_backfill(days: int) -> dict:
    """과거 N일 공시 일회성 수집. Daily cron의 작은 윈도우로는 영영 채워지지
    않는 역사적 gap 을 복구. rcept_no UNIQUE 로 중복 skip → idempotent.

    daily_collection 전체를 돌리는 대신 DART fetch + anomaly scan 만 실행.
    KRX/News 는 과거 데이터 의미 낮아 제외.
    """
    from app.services.collectors.dart import fetch_recent_disclosures
    from app.services.anomaly.detector import scan_new_disclosures

    t0 = datetime.now(timezone.utc)
    fetch_result: object = None
    anomaly_result: object = None
    fetch_err: str | None = None
    anomaly_err: str | None = None
    try:
        fetch_result = await fetch_recent_disclosures(days=days)
        logger.info("historical_backfill fetch: %s", fetch_result)
    except Exception as e:
        fetch_err = f"{type(e).__name__}: {e}"
        logger.exception("historical_backfill fetch failed")
    try:
        anomaly_result = await scan_new_disclosures()
        logger.info("historical_backfill anomaly: %s", anomaly_result)
    except Exception as e:
        anomaly_err = f"{type(e).__name__}: {e}"
        logger.exception("historical_backfill anomaly failed")
    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    return {
        "elapsed_seconds": round(dt, 1),
        "days": days,
        "fetch_result": fetch_result,
        "fetch_error": fetch_err,
        "anomaly_result": anomaly_result,
        "anomaly_error": anomaly_err,
    }


async def _run_daily_collection() -> dict:
    """Inline: scripts/scheduler.py:run_once(check_alerts=True) 와 동일."""
    from app.database import async_session
    from app.services.alert_service import check_and_alert
    from app.services.data_collector import collect_all

    t0 = datetime.now(timezone.utc)
    collect_result: object = None
    alert_result: object = None
    collect_err: str | None = None
    alert_err: str | None = None
    try:
        collect_result = await collect_all()
        logger.info("daily_collection collect_all: %s", collect_result)
    except Exception as e:
        collect_err = f"{type(e).__name__}: {e}"
        logger.exception("daily_collection collect_all failed")
    async with async_session() as db:
        try:
            alert_result = await check_and_alert(db)
            logger.info("daily_collection alerts: %s", alert_result)
        except Exception as e:
            alert_err = f"{type(e).__name__}: {e}"
            logger.exception("daily_collection check_and_alert failed")
    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    logger.info("daily_collection done elapsed=%.1fs", dt)
    return {
        "elapsed_seconds": round(dt, 1),
        "collect_result": collect_result,
        "collect_error": collect_err,
        "alert_result": alert_result,
        "alert_error": alert_err,
    }


@router.get("/")
async def list_jobs(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    """사용 가능한 job 목록 (디버깅용). 토큰 없으면 401/503."""
    _require_token(x_admin_token)
    return {jid: desc for jid, (_, desc) in JOBS.items()}


@router.post("/{job_id}")
async def trigger_job(
    job_id: str,
    days: int | None = None,
    start: str | None = None,
    cursor: str | None = None,
    max_new: int | None = None,
    ticker: str | None = None,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Job을 **동기적으로** 실행하고 완료 후 결과 반환.

    subprocess 경로는 `asyncio.to_thread`로 이벤트 루프를 블록하지 않고 돌림.
    subprocess가 최대 15분까지 걸려도 HTTP 응답을 대기시켜 Fly 머신이 깨어
    있게 유지 (BackgroundTasks 버전은 응답 즉시 Fly가 idle로 판단하고 머신을
    정지시켜 subprocess가 중단됐음, 2026-04-17 사건).

    Actions는 기본 6시간 timeout이라 안전. 워커 2개 중 1개가 길어야 몇 분
    블록되지만 크론은 간헐적이라 사용자 API와 겹치는 경우 드뭄.
    """
    _require_token(x_admin_token)
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")

    argv, desc = JOBS[job_id]
    started_at = datetime.now(timezone.utc).isoformat()

    if argv == "inline" and job_id == "daily_collection":
        result = await _run_daily_collection()
    elif argv == "inline" and job_id == "historical_backfill":
        # ?days=N 쿼리로 윈도우 지정. 없으면 30일. 7-90 clamp.
        d = max(7, min(90, days or 30))
        result = await _run_historical_backfill(d)
    elif argv == "inline" and job_id == "scan_anomalies_bulk":
        result = await _run_scan_anomalies_bulk()
    elif argv == "inline" and job_id == "sync_disclosures_all":
        from app.services.graph.sync import sync_all_disclosures
        result = await sync_all_disclosures()
    elif argv == "inline" and job_id == "backfill_year_gaps":
        # ?start=YYYY-MM-DD (default 2026-01-01), ?max_new=N (default 150, 0=무제한),
        # ?cursor=YYYY-MM-DD (optional resume point).
        mn = 150 if max_new is None else max(0, min(5000, max_new))
        result = await _run_backfill_year_gaps(
            start=start or "2026-01-01",
            max_new=mn,
            cursor=cursor,
        )
    elif argv == "inline" and job_id == "backfill_watchlist_governance":
        # ?days=N 이면 선행 per-ticker DART backfill 포함 (0-365 clamp, 0=skip).
        bd = max(0, min(365, days or 0))
        result = await _run_backfill_watchlist_governance(backfill_days=bd)
    elif argv == "inline" and job_id == "extract_governance_ticker":
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker query param required")
        from app.services.graph.extractor import extract_from_disclosures
        result = await extract_from_disclosures(ticker)
    elif argv == "inline" and job_id == "graph_ping":
        result = await _run_graph_ping()
    elif argv == "inline" and job_id == "extract_supply_chains":
        from app.services.graph.supply_chain_extractor import extract_supply_chains
        # 초기 bootstrap: 90일 / 최대 100건. 정기 운영 시엔 이 값을 줄일 것.
        result = await extract_supply_chains(days_back=90, max_filings=100)
    else:
        assert isinstance(argv, list)
        # `scan_earnings` / `scan_dividend_dates` / `scan_ex_dates_v2` 등 `--days N`
        # 인자를 쓰는 subprocess 잡은 query ?days=N 로 override 가능 — 120일 급
        # 일회성 backfill에 필요. 하드코딩된 기본값은 일상 cron용으로 유지.
        if days is not None and "--days" in argv:
            argv = list(argv)
            idx = argv.index("--days")
            argv[idx + 1] = str(max(1, min(365, days)))
        result = await asyncio.to_thread(_run_subprocess_sync, argv, job_id)

    return {
        "job": job_id,
        "description": desc,
        "started_at": started_at,
        "result": result,
    }

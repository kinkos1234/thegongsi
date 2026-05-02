"""공개 커버리지/품질 통계 — 랜딩과 기관 PoC 신뢰 신호."""
import csv
from datetime import datetime, timedelta, timezone
import io
import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import (
    CalendarEvent,
    Company,
    AdminJobRun,
    DDMemoVersion,
    Disclosure,
    DisclosureEvidence,
    EarningsEvent,
    EventReview,
)
from app.routers import get_current_user_optional
from app.services.organizations import current_organization_id

router = APIRouter()


def _parse_day(value) -> datetime | None:
    if not value:
        return None
    s = str(value)
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s[:10 if "-" in s else 8], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _disclosure_item(d: Disclosure, company_name: str | None = None) -> dict:
    return {
        "rcept_no": d.rcept_no,
        "ticker": d.ticker,
        "company": company_name,
        "title": d.report_nm,
        "date": d.rcept_dt,
        "severity": d.anomaly_severity,
        "summary": d.summary_ko,
        "dart_url": d.raw_url or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.rcept_no}",
    }


@router.get("/data-quality")
async def data_quality(
    days: int = 7,
    limit: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """Data quality drill-down for institutional readiness.

    Readiness gives aggregate status; this endpoint names the actual rows that
    need attention: missing classifications, missing summaries, missing
    severity evidence, possible company identity duplicates, and failed jobs.
    """
    days = max(1, min(90, days))
    limit = max(1, min(100, limit))
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).date().isoformat()

    unclassified_rows = (
        await db.execute(
            select(Disclosure, Company.name_ko)
            .join(Company, Company.ticker == Disclosure.ticker, isouter=True)
            .where(Disclosure.rcept_dt >= cutoff, Disclosure.anomaly_severity.is_(None))
            .order_by(Disclosure.rcept_dt.desc())
            .limit(limit)
        )
    ).all()
    missing_summary_rows = (
        await db.execute(
            select(Disclosure, Company.name_ko)
            .join(Company, Company.ticker == Disclosure.ticker, isouter=True)
            .where(Disclosure.rcept_dt >= cutoff, Disclosure.summary_ko.is_(None))
            .order_by(Disclosure.rcept_dt.desc())
            .limit(limit)
        )
    ).all()
    evidence_subq = select(DisclosureEvidence.rcept_no).where(DisclosureEvidence.kind == "severity")
    missing_evidence_rows = (
        await db.execute(
            select(Disclosure, Company.name_ko)
            .join(Company, Company.ticker == Disclosure.ticker, isouter=True)
            .where(
                Disclosure.rcept_dt >= cutoff,
                Disclosure.anomaly_severity.in_(["high", "med"]),
                Disclosure.rcept_no.not_in(evidence_subq),
            )
            .order_by(Disclosure.rcept_dt.desc())
            .limit(limit)
        )
    ).all()

    duplicate_name_rows = (
        await db.execute(
            select(Company.name_ko, func.count(Company.id).label("n"))
            .group_by(Company.name_ko)
            .having(func.count(Company.id) > 1)
            .order_by(func.count(Company.id).desc(), Company.name_ko.asc())
            .limit(20)
        )
    ).all()
    duplicate_names = [name for name, _count in duplicate_name_rows]
    duplicate_companies: list[dict] = []
    if duplicate_names:
        rows = (
            await db.execute(
                select(Company)
                .where(Company.name_ko.in_(duplicate_names))
                .order_by(Company.name_ko.asc(), Company.market.asc(), Company.ticker.asc())
            )
        ).scalars().all()
        grouped: dict[str, list[Company]] = {}
        for c in rows:
            grouped.setdefault(c.name_ko, []).append(c)
        actionable_groups = {
            name: companies
            for name, companies in grouped.items()
            if sum(1 for c in companies if c.market in ("KOSPI", "KOSDAQ")) > 1
        }
        duplicate_companies = [
            {
                "name": name,
                "count": len(companies),
                "companies": [
                    {"ticker": c.ticker, "corp_code": c.corp_code, "market": c.market}
                    for c in companies
                ],
            }
            for name, companies in actionable_groups.items()
        ][:20]

    failed_jobs = (
        await db.execute(
            select(AdminJobRun)
            .where(AdminJobRun.status == "failed")
            .order_by(AdminJobRun.started_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    issues = {
        "unclassified_disclosures": [_disclosure_item(d, name) for d, name in unclassified_rows],
        "missing_summaries": [_disclosure_item(d, name) for d, name in missing_summary_rows],
        "missing_severity_evidence": [_disclosure_item(d, name) for d, name in missing_evidence_rows],
        "duplicate_company_names": duplicate_companies,
        "failed_admin_jobs": [
            {
                "id": run.id,
                "job": run.job_id,
                "error": run.error,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "elapsed_seconds": run.elapsed_seconds,
            }
            for run in failed_jobs
        ],
    }
    counts = {key: len(value) for key, value in issues.items()}
    total_open = sum(counts.values())

    return {
        "as_of": now.isoformat(),
        "window_days": days,
        "limit": limit,
        "status": "pass" if total_open == 0 else "warn",
        "counts": counts,
        "issues": issues,
    }


@router.get("/quality/severity")
async def severity_quality():
    """Rule-based severity classifier quality report against the curated gold set."""
    from app.services.quality.severity_eval import evaluate_default_gold

    report = evaluate_default_gold()
    report["as_of"] = datetime.now(timezone.utc).isoformat()
    return report


@router.get("/quality/severity/sample")
async def severity_labeling_sample(
    days: int = 30,
    per_label: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Stratified live-disclosure sample for expanding the severity gold set."""
    from app.services.quality.severity_sampling import build_labeling_sample

    sample = await build_labeling_sample(db, days=days, per_label=per_label)
    sample["as_of"] = datetime.now(timezone.utc).isoformat()
    return sample


@router.get("/quality/severity/sample.csv")
async def severity_labeling_sample_csv(
    days: int = 30,
    per_label: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """CSV labeling sheet for severity gold-set expansion."""
    from app.services.quality.severity_sampling import build_labeling_sample

    sample = await build_labeling_sample(db, days=days, per_label=per_label)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "label",
        "label_note",
        "predicted",
        "rcept_no",
        "ticker",
        "company",
        "date",
        "title",
        "reason",
        "rule_set",
        "dart_url",
    ])
    for item in sample["items"]:
        writer.writerow([
            item["label"],
            item["label_note"],
            item["predicted"],
            item["rcept_no"],
            item["ticker"],
            item["company"] or "",
            item["date"],
            item["title"],
            item["reason"],
            item["rule_set"],
            item["dart_url"],
        ])
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="severity-labeling-sample.csv"'},
    )


@router.get("/coverage")
async def coverage(db: AsyncSession = Depends(get_db)):
    """총 공시 수, 커버되는 기업 수, 최근 7일 이상 공시 수, since, 일평균.

    랜딩 "오늘의 이상 공시" 상단에 트러스트 시그널 + 내러티브로 노출.
    """
    total_disclosures = (
        await db.execute(select(func.count(Disclosure.id)))
    ).scalar_one()
    total_companies = (
        await db.execute(select(func.count(Company.id)))
    ).scalar_one()
    # rcept_dt는 YYYY-MM-DD 형식으로 저장됨(예: "2026-04-15").
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    anomalies_7d = (
        await db.execute(
            select(func.count(Disclosure.id)).where(
                Disclosure.anomaly_severity.in_(["high", "med"]),
                Disclosure.rcept_dt >= cutoff,
            )
        )
    ).scalar_one()
    since = (
        await db.execute(select(func.min(Disclosure.rcept_dt)))
    ).scalar_one()
    since_iso = None
    daily_avg = None
    if since:
        s = str(since)
        # YYYY-MM-DD 또는 YYYYMMDD 양쪽 수용
        try:
            since_dt = _parse_day(s)
            if since_dt is None:
                raise ValueError
            since_iso = since_dt.date().isoformat()
            days = max(1, (datetime.now(timezone.utc) - since_dt).days)
            daily_avg = round(int(total_disclosures or 0) / days, 1)
        except ValueError:
            pass

    return {
        "disclosures": int(total_disclosures or 0),
        "companies": int(total_companies or 0),
        "anomalies_7d": int(anomalies_7d or 0),
        "since": since_iso,
        "daily_avg": daily_avg,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ask-suggestions")
async def ask_suggestions(db: AsyncSession = Depends(get_db)):
    """오늘 시점에 던지면 의미 있는 질의 3-5개.

    최근 7일 high+med 공시에서 섹터·키워드를 뽑아 동적 생성.
    백엔드가 맥락 없으면 기본 5개 fallback.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y%m%d")
    res = await db.execute(
        select(Disclosure)
        .where(
            Disclosure.anomaly_severity.in_(["high", "med"]),
            Disclosure.rcept_dt >= cutoff,
        )
        .order_by(Disclosure.rcept_dt.desc())
        .limit(30)
    )
    rows = list(res.scalars().all())

    suggestions: list[str] = []
    seen_sectors: set[str] = set()

    # Company 섹터 lookup
    if rows:
        tickers = list({d.ticker for d in rows})
        crs = await db.execute(select(Company).where(Company.ticker.in_(tickers)))
        sector_map = {c.ticker: c.sector for c in crs.scalars().all() if c.sector}
        for d in rows:
            sec = sector_map.get(d.ticker)
            if sec and sec not in seen_sectors:
                seen_sectors.add(sec)
                suggestions.append(f"{sec} 섹터의 최근 이상 공시")
                if len(suggestions) >= 3:
                    break

    keyword_triggers = {
        "유상증자": "최근 1주일 유상증자 공시한 코스닥 종목",
        "감사의견": "최근 감사의견 '한정'·'의견거절' 공시",
        "최대주주": "최근 최대주주 변경 공시 요약",
        "소송": "진행 중 소송 관련 공시 TOP 5",
        "배당": "이번 주 배당 관련 공시",
    }
    for kw, q in keyword_triggers.items():
        if any(kw in (d.report_nm or "") for d in rows):
            suggestions.append(q)
        if len(suggestions) >= 5:
            break

    # Fallback — 공시 데이터 적거나 쿼리 비어있을 때
    fallback = [
        "HBM 공급망에서 최근 이상 공시가 있는 회사?",
        "최근 1주일 감사의견 변경·한정 공시",
        "SK하이닉스의 주요 공급처와 최근 공시",
        "최대주주 변경이 있었던 코스닥 종목",
        "삼성전자 관련된 자회사·계열사 중 배당 공시",
    ]
    while len(suggestions) < 5:
        fb = fallback.pop(0) if fallback else None
        if not fb:
            break
        if fb not in suggestions:
            suggestions.append(fb)

    return {"suggestions": suggestions[:5]}


@router.get("/pulse")
async def pulse(days: int = 30, db: AsyncSession = Depends(get_db)):
    """최근 N일간 일별 이상 공시(high+med) 카운트 — 히어로 빈 상태 폴백용 리본.

    rcept_dt가 YYYYMMDD 문자열이어서 SUBSTR로 day 파티션. SQLite/Postgres 양쪽 호환.
    """
    from sqlalchemy import literal_column

    days = max(7, min(90, days))
    # rcept_dt는 YYYY-MM-DD 형식
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    res = await db.execute(
        select(
            Disclosure.rcept_dt.label("d"),
            func.count(Disclosure.id).label("n"),
        )
        .where(
            Disclosure.rcept_dt >= cutoff,
            Disclosure.anomaly_severity.in_(["high", "med"]),
        )
        .group_by(Disclosure.rcept_dt)
        .order_by(literal_column("d"))
    )
    rows = [{"date": str(r.d), "count": int(r.n)} for r in res.all()]
    return {"days": days, "series": rows}


@router.get("/readiness")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Institutional PoC readiness snapshot.

    This is not a compliance certification. It exposes operational evidence that
    an investor or asset-manager evaluator can inspect before trusting the demo:
    data freshness, coverage, anomaly triage volume, and memo evidence metadata.
    """
    now = datetime.now(timezone.utc)

    total_disclosures = (await db.execute(select(func.count(Disclosure.id)))).scalar_one()
    total_companies = (await db.execute(select(func.count(Company.id)))).scalar_one()
    latest_disclosure = (await db.execute(select(func.max(Disclosure.rcept_dt)))).scalar_one()
    latest_dt = _parse_day(latest_disclosure)
    latest_age_days = (now.date() - latest_dt.date()).days if latest_dt else None

    cutoff_7d = (now - timedelta(days=7)).date().isoformat()
    recent_7d = (
        await db.execute(
            select(func.count(Disclosure.id)).where(Disclosure.rcept_dt >= cutoff_7d)
        )
    ).scalar_one()
    anomalies_7d = (
        await db.execute(
            select(func.count(Disclosure.id)).where(
                Disclosure.rcept_dt >= cutoff_7d,
                Disclosure.anomaly_severity.in_(["high", "med"]),
            )
        )
    ).scalar_one()
    anomalies_with_evidence_7d = (
        await db.execute(
            select(func.count(func.distinct(DisclosureEvidence.rcept_no)))
            .join(Disclosure, Disclosure.rcept_no == DisclosureEvidence.rcept_no)
            .where(
                Disclosure.rcept_dt >= cutoff_7d,
                Disclosure.anomaly_severity.in_(["high", "med"]),
                DisclosureEvidence.kind == "severity",
            )
        )
    ).scalar_one()
    unclassified_7d = (
        await db.execute(
            select(func.count(Disclosure.id)).where(
                Disclosure.rcept_dt >= cutoff_7d,
                Disclosure.anomaly_severity.is_(None),
            )
        )
    ).scalar_one()
    missing_summary_7d = (
        await db.execute(
            select(func.count(Disclosure.id)).where(
                Disclosure.rcept_dt >= cutoff_7d,
                Disclosure.summary_ko.is_(None),
            )
        )
    ).scalar_one()

    latest_earnings = (await db.execute(select(func.max(EarningsEvent.reported_date)))).scalar_one()
    latest_calendar = (await db.execute(select(func.max(CalendarEvent.event_date)))).scalar_one()
    cutoff_24h = now.replace(tzinfo=None) - timedelta(hours=24)
    admin_runs_24h = (
        await db.execute(
            select(func.count(AdminJobRun.id)).where(AdminJobRun.started_at >= cutoff_24h)
        )
    ).scalar_one()
    admin_failed_24h = (
        await db.execute(
            select(func.count(AdminJobRun.id)).where(
                AdminJobRun.started_at >= cutoff_24h,
                AdminJobRun.status == "failed",
            )
        )
    ).scalar_one()
    latest_admin_run = (
        await db.execute(select(func.max(AdminJobRun.started_at)))
    ).scalar_one()

    memo_total = (await db.execute(select(func.count(DDMemoVersion.id)))).scalar_one()
    memo_rows = (
        await db.execute(
            select(DDMemoVersion.sources, DDMemoVersion.generated_by)
            .order_by(DDMemoVersion.created_at.desc())
            .limit(100)
        )
    ).all()
    memo_with_sources = 0
    memo_with_model = 0
    for sources_raw, generated_by in memo_rows:
        if generated_by:
            memo_with_model += 1
        try:
            sources = json.loads(sources_raw or "[]")
        except json.JSONDecodeError:
            sources = []
        if any(s.get("type") == "disclosure" and s.get("rcept_no") for s in sources if isinstance(s, dict)):
            memo_with_sources += 1

    checks = [
        {
            "id": "fresh_disclosures",
            "label": "DART freshness",
            # DART has sparse weekends/market holidays; a 2-3 calendar-day gap
            # after the latest business filing is not by itself stale.
            "status": "pass" if latest_age_days is not None and latest_age_days <= 3 else "warn",
            "detail": f"latest={latest_disclosure or '-'} age_days={latest_age_days if latest_age_days is not None else '-'}",
        },
        {
            "id": "coverage",
            "label": "Company coverage",
            "status": "pass" if int(total_companies or 0) >= 3500 else "warn",
            "detail": f"{int(total_companies or 0):,} companies",
        },
        {
            "id": "severity_classification",
            "label": "Severity classification",
            "status": "pass" if int(recent_7d or 0) and int(unclassified_7d or 0) == 0 else "warn",
            "detail": f"unclassified_7d={int(unclassified_7d or 0):,}",
        },
        {
            "id": "severity_evidence",
            "label": "Severity evidence coverage",
            "status": (
                "pass"
                if int(anomalies_7d or 0) == 0
                or int(anomalies_with_evidence_7d or 0) == int(anomalies_7d or 0)
                else "warn"
            ),
            "detail": (
                f"{int(anomalies_with_evidence_7d or 0):,}/"
                f"{int(anomalies_7d or 0):,} high/med anomalies have severity evidence"
            ),
        },
        {
            "id": "memo_evidence",
            "label": "Memo evidence metadata",
            "status": "pass" if memo_rows and memo_with_sources == len(memo_rows) else "warn",
            "detail": f"{memo_with_sources}/{len(memo_rows)} sampled memo versions have disclosure sources",
        },
        {
            "id": "admin_job_audit",
            "label": "Admin job audit trail",
            "status": "pass" if int(admin_runs_24h or 0) > 0 and int(admin_failed_24h or 0) == 0 else "warn",
            "detail": f"runs_24h={int(admin_runs_24h or 0):,} failed_24h={int(admin_failed_24h or 0):,}",
        },
    ]
    score = round(sum(1 for c in checks if c["status"] == "pass") / len(checks) * 100)

    return {
        "as_of": now.isoformat(),
        "score": score,
        "status": "poc_ready" if score >= 75 else "needs_attention",
        "coverage": {
            "companies": int(total_companies or 0),
            "disclosures": int(total_disclosures or 0),
            "latest_disclosure_date": latest_disclosure,
            "latest_disclosure_age_days": latest_age_days,
            "recent_7d": int(recent_7d or 0),
            "anomalies_7d": int(anomalies_7d or 0),
            "unclassified_7d": int(unclassified_7d or 0),
            "missing_summary_7d": int(missing_summary_7d or 0),
            "latest_earnings_reported_date": latest_earnings,
            "latest_calendar_event_date": latest_calendar,
        },
        "memo_evidence": {
            "total_versions": int(memo_total or 0),
            "sampled_versions": len(memo_rows),
            "with_disclosure_sources": memo_with_sources,
            "with_model_metadata": memo_with_model,
        },
        "disclosure_evidence": {
            "anomalies_7d": int(anomalies_7d or 0),
            "with_severity_evidence_7d": int(anomalies_with_evidence_7d or 0),
        },
        "operations": {
            "admin_runs_24h": int(admin_runs_24h or 0),
            "admin_failed_24h": int(admin_failed_24h or 0),
            "latest_admin_run": latest_admin_run.isoformat() if latest_admin_run else None,
        },
        "checks": checks,
    }


@router.get("/event-inbox")
async def event_inbox(
    days: int = 7,
    limit: int = 50,
    user=Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Analyst-facing disclosure triage queue.

    This endpoint packages high/medium severity filings as an inbox instead of a
    generic feed. Review state is intentionally ephemeral for now; the next
    iteration can persist analyst decisions per user/team.
    """
    days = max(1, min(30, days))
    limit = max(1, min(200, limit))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    res = await db.execute(
        select(Disclosure, Company.name_ko, Company.market, Company.sector)
        .join(Company, Company.ticker == Disclosure.ticker, isouter=True)
        .where(
            Disclosure.rcept_dt >= cutoff,
            Disclosure.anomaly_severity.in_(["high", "med"]),
        )
        .order_by(Disclosure.rcept_dt.desc(), Disclosure.anomaly_severity.asc())
        .limit(limit)
    )
    rows = res.all()
    review_map: dict[str, EventReview] = {}
    if user and rows:
        org_id = await current_organization_id(db, user)
        rcepts = [d.rcept_no for d, *_ in rows]
        review_rows = (
            await db.execute(
                select(EventReview).where(
                    EventReview.organization_id == org_id,
                    EventReview.rcept_no.in_(rcepts),
                )
            )
        ).scalars().all()
        review_map = {r.rcept_no: r for r in review_rows}

    items = []
    for d, name, market, sector in rows:
        severity = d.anomaly_severity or "uncertain"
        review = review_map.get(d.rcept_no)
        items.append(
            {
                "id": d.rcept_no,
                "status": review.status if review else "new",
                "review_note": review.note if review else None,
                "reviewed_by_user_id": review.reviewed_by_user_id if review else None,
                "reviewed_at": review.updated_at.isoformat() if review and review.updated_at else None,
                "severity": severity,
                "priority": 1 if severity == "high" else 2,
                "ticker": d.ticker,
                "company": name,
                "market": market,
                "sector": sector,
                "date": d.rcept_dt,
                "title": d.report_nm,
                "reason": d.anomaly_reason,
                "summary": d.summary_ko,
                "evidence": {
                    "rcept_no": d.rcept_no,
                    "dart_url": d.raw_url
                    or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.rcept_no}",
                },
                "actions": ["review", "dismiss", "escalate"],
            }
        )
    counts = {
        "high": sum(1 for item in items if item["severity"] == "high"),
        "med": sum(1 for item in items if item["severity"] == "med"),
        "new": sum(1 for item in items if item["status"] == "new"),
        "reviewed": sum(1 for item in items if item["status"] == "reviewed"),
        "dismissed": sum(1 for item in items if item["status"] == "dismissed"),
        "escalated": sum(1 for item in items if item["status"] == "escalated"),
    }
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "limit": limit,
        "counts": counts,
        "items": items,
    }

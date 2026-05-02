"""Sampling utilities to expand severity gold labels from real disclosures."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Company, Disclosure
from app.services.anomaly.detector import RULE_SET_VERSION, rule_based_match

LABELS = ("high", "med", "low")


def _normalize_prediction(label: str | None) -> str:
    return label if label in LABELS else "low"


def _candidate_payload(d: Disclosure, company_name: str | None) -> dict:
    predicted_raw, reason, evidence = rule_based_match(d.report_nm)
    predicted = _normalize_prediction(predicted_raw)
    return {
        "rcept_no": d.rcept_no,
        "ticker": d.ticker,
        "company": company_name,
        "date": d.rcept_dt,
        "title": d.report_nm,
        "summary": d.summary_ko,
        "predicted": predicted,
        "reason": reason or "규칙 매칭 없음",
        "evidence": evidence,
        "rule_set": RULE_SET_VERSION,
        "label": "",
        "label_note": "",
        "dart_url": d.raw_url or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.rcept_no}",
    }


async def build_labeling_sample(
    db: AsyncSession,
    *,
    days: int = 30,
    per_label: int = 20,
) -> dict:
    """Return a stratified labeling sample by predicted severity.

    The sample is deliberately based on live DB rows, not handcrafted titles, so
    analysts can grow the gold set from real distributional examples.
    """
    days = max(1, min(365, days))
    per_label = max(1, min(200, per_label))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    rows = (
        await db.execute(
            select(Disclosure, Company.name_ko)
            .join(Company, Company.ticker == Disclosure.ticker, isouter=True)
            .where(Disclosure.rcept_dt >= cutoff)
            .order_by(Disclosure.rcept_dt.desc(), Disclosure.rcept_no.desc())
            .limit(5000)
        )
    ).all()

    buckets: dict[str, list[dict]] = {label: [] for label in LABELS}
    for disclosure, company_name in rows:
        item = _candidate_payload(disclosure, company_name)
        bucket = item["predicted"]
        if len(buckets[bucket]) < per_label:
            buckets[bucket].append(item)
        if all(len(items) >= per_label for items in buckets.values()):
            break

    items = [item for label in LABELS for item in buckets[label]]
    return {
        "suite": "severity_labeling_sample_v1",
        "rule_set": RULE_SET_VERSION,
        "window_days": days,
        "per_label": per_label,
        "counts": {label: len(buckets[label]) for label in LABELS},
        "items": items,
    }

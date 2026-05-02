"""Analyst event review workflow."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Disclosure, EventReview
from app.models._base import utc_now
from app.routers import get_current_user
from app.services.organizations import current_organization_id

router = APIRouter()

VALID_STATUSES = {"reviewed", "dismissed", "escalated"}


class ReviewRequest(BaseModel):
    rcept_no: str
    status: str = Field(pattern="^(reviewed|dismissed|escalated)$")
    note: str | None = Field(None, max_length=2000)


@router.post("/reviews")
async def upsert_review(
    req: ReviewRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    disclosure = (
        await db.execute(select(Disclosure).where(Disclosure.rcept_no == req.rcept_no))
    ).scalar_one_or_none()
    if not disclosure:
        raise HTTPException(status_code=404, detail="disclosure not found")

    org_id = await current_organization_id(db, user)
    existing = (
        await db.execute(
            select(EventReview).where(
                EventReview.organization_id == org_id,
                EventReview.rcept_no == req.rcept_no,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.status = req.status
        existing.note = req.note
        existing.reviewed_by_user_id = user.id
        existing.updated_at = utc_now()
        review = existing
    else:
        review = EventReview(
            user_id=user.id,
            organization_id=org_id,
            reviewed_by_user_id=user.id,
            rcept_no=req.rcept_no,
            status=req.status,
            note=req.note,
        )
        db.add(review)
    await db.commit()
    await db.refresh(review)
    return {
        "status": "recorded",
        "review": {
            "rcept_no": review.rcept_no,
            "organization_id": review.organization_id,
            "review_status": review.status,
            "note": review.note,
            "reviewed_by_user_id": review.reviewed_by_user_id,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        },
    }


@router.get("/reviews")
async def list_reviews(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await current_organization_id(db, user)
    rows = (
        await db.execute(
            select(EventReview, Disclosure)
            .join(Disclosure, Disclosure.rcept_no == EventReview.rcept_no, isouter=True)
            .where(EventReview.organization_id == org_id)
            .order_by(EventReview.updated_at.desc())
            .limit(200)
        )
    ).all()
    return [
        {
            "rcept_no": r.rcept_no,
            "organization_id": r.organization_id,
            "review_status": r.status,
            "note": r.note,
            "reviewed_by_user_id": r.reviewed_by_user_id,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "ticker": d.ticker if d else None,
            "title": d.report_nm if d else None,
            "date": d.rcept_dt if d else None,
            "severity": d.anomaly_severity if d else None,
        }
        for r, d in rows
    ]


@router.get("/reviews/summary")
async def review_summary(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await current_organization_id(db, user)
    rows = (
        await db.execute(
            select(EventReview.status, func.count(EventReview.id))
            .where(EventReview.organization_id == org_id)
            .group_by(EventReview.status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    return {
        "reviewed": counts.get("reviewed", 0),
        "dismissed": counts.get("dismissed", 0),
        "escalated": counts.get("escalated", 0),
        "total": sum(counts.values()),
    }


@router.get("/reviews/export.csv")
async def export_reviews_csv(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org_id = await current_organization_id(db, user)
    rows = (
        await db.execute(
            select(EventReview, Disclosure)
            .join(Disclosure, Disclosure.rcept_no == EventReview.rcept_no, isouter=True)
            .where(EventReview.organization_id == org_id)
            .order_by(EventReview.updated_at.desc())
            .limit(1000)
        )
    ).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "rcept_no",
        "status",
        "ticker",
        "date",
        "severity",
        "title",
        "note",
        "updated_at",
        "dart_url",
    ])
    for r, d in rows:
        writer.writerow([
            r.rcept_no,
            r.status,
            d.ticker if d else "",
            d.rcept_dt if d else "",
            d.anomaly_severity if d else "",
            d.report_nm if d else "",
            r.note or "",
            r.updated_at.isoformat() if r.updated_at else "",
            (d.raw_url if d and d.raw_url else f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r.rcept_no}"),
        ])
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="thegongsi-event-reviews.csv"'},
    )

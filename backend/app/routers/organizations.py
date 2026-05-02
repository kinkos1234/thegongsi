"""Organization/workspace endpoints."""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models._base import utc_now
from app.models.tables import Organization, OrganizationInvite, OrganizationMember
from app.routers import get_current_user
from app.services.organizations import ensure_personal_organization, require_org_role

router = APIRouter()
MANAGER_ROLES = {"owner", "admin"}
VALID_INVITE_ROLES = {"admin", "analyst", "viewer"}


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="analyst", pattern="^(admin|analyst|viewer)$")


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=16, max_length=120)


@router.get("/me")
async def my_organization(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org = await ensure_personal_organization(db, user)
    await db.commit()
    members = (
        await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
            .order_by(OrganizationMember.created_at.asc())
        )
    ).scalars().all()
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "members": [
            {
                "user_id": m.user_id,
                "role": m.role,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in members
        ],
    }


@router.get("/invitations")
async def list_invitations(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org, _membership = await require_org_role(db, user, MANAGER_ROLES)
    rows = (
        await db.execute(
            select(OrganizationInvite)
            .where(OrganizationInvite.organization_id == org.id)
            .order_by(OrganizationInvite.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return {
        "organization_id": org.id,
        "invitations": [
            {
                "id": row.id,
                "email": row.email,
                "role": row.role,
                "status": row.status,
                "token": row.token if row.status == "pending" else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
            }
            for row in rows
        ],
    }


@router.post("/invitations")
async def create_invitation(
    req: InviteRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org, _membership = await require_org_role(db, user, MANAGER_ROLES)
    email = req.email.lower()
    existing = (
        await db.execute(
            select(OrganizationInvite).where(
                OrganizationInvite.organization_id == org.id,
                OrganizationInvite.email == email,
                OrganizationInvite.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing:
        invite = existing
        invite.role = req.role
    else:
        invite = OrganizationInvite(
            organization_id=org.id,
            email=email,
            role=req.role,
            token=secrets.token_urlsafe(32),
            status="pending",
            invited_by_user_id=user.id,
        )
        db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return {
        "id": invite.id,
        "organization_id": org.id,
        "email": invite.email,
        "role": invite.role,
        "status": invite.status,
        "token": invite.token,
    }


@router.post("/invitations/accept")
async def accept_invitation(
    req: AcceptInviteRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = (
        await db.execute(
            select(OrganizationInvite).where(
                OrganizationInvite.token == req.token,
                OrganizationInvite.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="invitation not found")
    if user.email.lower() != invite.email.lower():
        raise HTTPException(status_code=403, detail="invitation email mismatch")

    existing = (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == invite.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = invite.role
        membership = existing
    else:
        membership = OrganizationMember(
            organization_id=invite.organization_id,
            user_id=user.id,
            role=invite.role,
        )
        db.add(membership)
    user.default_organization_id = invite.organization_id
    invite.status = "accepted"
    invite.accepted_by_user_id = user.id
    invite.accepted_at = utc_now()
    await db.commit()
    await db.refresh(membership)
    return {
        "status": "accepted",
        "organization_id": invite.organization_id,
        "role": membership.role,
    }

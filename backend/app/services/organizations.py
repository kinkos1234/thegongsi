from __future__ import annotations

import asyncio
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.tables import Organization, OrganizationMember, User

_ORG_BOOTSTRAP_LOCKS: dict[str, asyncio.Lock] = {}


def _slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base or "workspace"


async def ensure_personal_organization(db: AsyncSession, user: User) -> Organization:
    """Create a default organization for a user if one does not already exist."""
    user_id = user.id
    lock = _ORG_BOOTSTRAP_LOCKS.setdefault(user_id, asyncio.Lock())
    async with lock:
        return await _ensure_personal_organization_locked(db, user, user_id)


async def _ensure_personal_organization_locked(
    db: AsyncSession,
    user: User,
    user_id: str,
) -> Organization:
    if user.default_organization_id:
        existing = await db.get(Organization, user.default_organization_id)
        if existing:
            return existing

    membership_org = (
        await db.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(OrganizationMember.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if membership_org:
        user.default_organization_id = membership_org.id
        await db.flush()
        return membership_org

    local_part = user.email.split("@", 1)[0]
    base_slug = _slugify(user.email)
    slug = base_slug
    suffix = 1
    while True:
        row = (await db.execute(select(Organization).where(Organization.slug == slug))).scalar_one_or_none()
        if row:
            suffix += 1
            slug = f"{base_slug}-{suffix}"
            continue

        org = Organization(name=f"{user.name or local_part} workspace", slug=slug)
        try:
            db.add(org)
            await db.flush()
            db.add(OrganizationMember(organization_id=org.id, user_id=user_id, role="owner"))
            user.default_organization_id = org.id
            await db.flush()
        except IntegrityError:
            await db.rollback()
            fresh_user = await db.get(User, user_id)
            existing = (
                await db.execute(
                    select(Organization)
                    .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                    .where(OrganizationMember.user_id == user_id)
                    .order_by(OrganizationMember.created_at.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing:
                if fresh_user:
                    fresh_user.default_organization_id = existing.id
                await db.flush()
                return existing
            suffix += 1
            slug = f"{base_slug}-{suffix}"
            continue
        return org


async def current_organization_id(db: AsyncSession, user: User) -> str:
    org = await ensure_personal_organization(db, user)
    return org.id


async def get_membership(db: AsyncSession, user_id: str, organization_id: str) -> OrganizationMember | None:
    return (
        await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()


async def require_org_role(
    db: AsyncSession,
    user: User,
    allowed_roles: set[str] | None = None,
) -> tuple[Organization, OrganizationMember]:
    org = await ensure_personal_organization(db, user)
    membership = await get_membership(db, user.id, org.id)
    if not membership:
        raise HTTPException(status_code=403, detail="organization membership required")
    if allowed_roles and membership.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="insufficient organization role")
    return org, membership

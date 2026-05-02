import asyncio

import pytest
import bcrypt as _bcrypt
from sqlalchemy import func, select

from app.database import async_session
from app.models.tables import Company, Disclosure, Organization, OrganizationInvite, OrganizationMember, User


async def _register(client, email: str):
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "pw12345678", "name": email.split("@", 1)[0]},
    )
    assert r.status_code == 200
    return r.json()


async def _seed_event():
    async with async_session() as db:
        db.add(Company(ticker="005930", corp_code="00126380", name_ko="삼성전자", market="KOSPI"))
        db.add(
            Disclosure(
                rcept_no="20260502000001",
                corp_code="00126380",
                ticker="005930",
                report_nm="주요사항보고서(유상증자결정)",
                rcept_dt="2026-05-02",
                anomaly_severity="high",
                anomaly_reason="자금조달 이벤트",
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_register_creates_default_organization(client):
    auth = await _register(client, "owner@example.com")
    token = auth["token"]

    assert auth["user"]["organization_id"]

    r = await client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == auth["user"]["organization_id"]
    assert body["members"][0]["role"] == "owner"


@pytest.mark.asyncio
async def test_legacy_user_concurrent_org_bootstrap_is_idempotent(client):
    async with async_session() as db:
        db.add(
            User(
                email="legacy-org@example.com",
                password_hash=_bcrypt.hashpw(b"pw12345678", _bcrypt.gensalt()).decode(),
                name="legacy",
            )
        )
        await db.commit()

    auth = await client.post(
        "/api/auth/login",
        json={"email": "legacy-org@example.com", "password": "pw12345678"},
    )
    assert auth.status_code == 200
    token = auth.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    org_res, invites_res = await asyncio.gather(
        client.get("/api/orgs/me", headers=headers),
        client.get("/api/orgs/invitations", headers=headers),
    )

    assert org_res.status_code == 200
    assert invites_res.status_code == 200
    org_id = org_res.json()["id"]
    assert invites_res.json()["organization_id"] == org_id

    async with async_session() as db:
        user = (await db.execute(select(User).where(User.email == "legacy-org@example.com"))).scalar_one()
        member_count = (
            await db.execute(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.user_id == user.id))
        ).scalar_one()
        org_count = (
            await db.execute(select(func.count()).select_from(Organization).where(Organization.slug.like("legacy-org-example-com%")))
        ).scalar_one()

    assert user.default_organization_id == org_id
    assert member_count == 1
    assert org_count == 1


@pytest.mark.asyncio
async def test_event_reviews_are_shared_within_organization(client):
    await _seed_event()
    owner = await _register(client, "team-owner@example.com")
    analyst = await _register(client, "team-analyst@example.com")
    owner_org_id = owner["user"]["organization_id"]

    async with async_session() as db:
        analyst_user = (
            await db.execute(select(User).where(User.email == "team-analyst@example.com"))
        ).scalar_one()
        analyst_id = analyst_user.id
        db.add(OrganizationMember(organization_id=owner_org_id, user_id=analyst_id, role="analyst"))
        analyst_user.default_organization_id = owner_org_id
        await db.commit()

    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    analyst_headers = {"Authorization": f"Bearer {analyst['token']}"}
    r = await client.post(
        "/api/events/reviews",
        json={"rcept_no": "20260502000001", "status": "escalated", "note": "공동 검토"},
        headers=owner_headers,
    )
    assert r.status_code == 200
    assert r.json()["review"]["organization_id"] == owner_org_id

    r = await client.get("/api/stats/event-inbox?days=7&limit=10", headers=analyst_headers)
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["status"] == "escalated"
    assert item["review_note"] == "공동 검토"

    r = await client.get("/api/events/reviews/summary", headers=analyst_headers)
    assert r.status_code == 200
    assert r.json()["escalated"] == 1


@pytest.mark.asyncio
async def test_owner_can_invite_and_user_can_accept(client):
    owner = await _register(client, "invite-owner@example.com")
    invitee = await _register(client, "invitee@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    invitee_headers = {"Authorization": f"Bearer {invitee['token']}"}

    r = await client.post(
        "/api/orgs/invitations",
        json={"email": "invitee@example.com", "role": "analyst"},
        headers=owner_headers,
    )

    assert r.status_code == 200
    invite = r.json()
    assert invite["organization_id"] == owner["user"]["organization_id"]
    assert invite["token"]

    r = await client.post(
        "/api/orgs/invitations/accept",
        json={"token": invite["token"]},
        headers=invitee_headers,
    )

    assert r.status_code == 200
    assert r.json()["organization_id"] == owner["user"]["organization_id"]
    assert r.json()["role"] == "analyst"

    r = await client.get("/api/orgs/me", headers=invitee_headers)
    assert r.status_code == 200
    assert r.json()["id"] == owner["user"]["organization_id"]
    assert any(m["user_id"] == invitee["user"]["id"] and m["role"] == "analyst" for m in r.json()["members"])

    async with async_session() as db:
        row = (
            await db.execute(select(OrganizationInvite).where(OrganizationInvite.token == invite["token"]))
        ).scalar_one()
    assert row.status == "accepted"


@pytest.mark.asyncio
async def test_non_manager_cannot_invite(client):
    owner = await _register(client, "perm-owner@example.com")
    viewer = await _register(client, "perm-viewer@example.com")
    async with async_session() as db:
        viewer_user = (
            await db.execute(select(User).where(User.email == "perm-viewer@example.com"))
        ).scalar_one()
        viewer_user.default_organization_id = owner["user"]["organization_id"]
        db.add(
            OrganizationMember(
                organization_id=owner["user"]["organization_id"],
                user_id=viewer_user.id,
                role="viewer",
            )
        )
        await db.commit()

    r = await client.post(
        "/api/orgs/invitations",
        json={"email": "blocked@example.com", "role": "analyst"},
        headers={"Authorization": f"Bearer {viewer['token']}"},
    )

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_invitation_email_must_match_authenticated_user(client):
    owner = await _register(client, "mismatch-owner@example.com")
    other = await _register(client, "mismatch-other@example.com")

    r = await client.post(
        "/api/orgs/invitations",
        json={"email": "target@example.com", "role": "viewer"},
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/orgs/invitations/accept",
        json={"token": r.json()["token"]},
        headers={"Authorization": f"Bearer {other['token']}"},
    )

    assert r.status_code == 403

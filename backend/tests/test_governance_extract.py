"""On-demand governance extraction 엔드포인트 가드 로직 테스트.

실제 Claude/DART 호출은 비용·외부의존이라 건너뛰고, 응답 빠른 paths만 커버:
- 404: ticker 미존재
- already_extracted: 기존 스냅샷 있으면 추출 건너뜀
- cooldown: 같은 ticker 1시간 내 재요청
- ip_limit: 시간당 3회 초과
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.database import async_session
from app.models.tables import (
    Company,
    GovernanceExtractRequest,
    MajorShareholder,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_company(ticker: str = "005930"):
    async with async_session() as db:
        db.add(Company(
            ticker=ticker,
            corp_code=f"CORP{ticker}",
            name_ko="테스트",
            market="KOSPI",
        ))
        await db.commit()


@pytest.mark.asyncio
async def test_extract_unknown_ticker_returns_404(client):
    r = await client.post("/api/companies/999999/governance/extract")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_extract_already_extracted(client):
    await _seed_company()
    async with async_session() as db:
        db.add(MajorShareholder(
            ticker="005930", holder_name="이재용", holder_type="person",
            stake_pct=1.5, as_of="2026-01-01",
        ))
        await db.commit()
    r = await client.post("/api/companies/005930/governance/extract")
    assert r.status_code == 200
    assert r.json()["status"] == "already_extracted"


@pytest.mark.asyncio
async def test_extract_cooldown(client):
    # company + 최근 request (processing) 존재 → cooldown 경로
    await _seed_company()
    async with async_session() as db:
        db.add(GovernanceExtractRequest(
            ticker="005930", status="processing",
            requested_at=_utc_now() - timedelta(minutes=5),
            requester_ip="1.2.3.4",
        ))
        await db.commit()
    r = await client.post("/api/companies/005930/governance/extract")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "cooldown"
    assert "next_eligible_at" in body


@pytest.mark.asyncio
async def test_extract_ip_limit(client):
    # 서로 다른 ticker 3개 + 같은 IP의 최근 시도 3건 → 4번째 ticker에서 ip_limit
    for t in ("005930", "000660", "035420", "373220"):
        await _seed_company(t)
    async with async_session() as db:
        for t in ("005930", "000660", "035420"):
            db.add(GovernanceExtractRequest(
                ticker=t, status="done",
                requested_at=_utc_now() - timedelta(hours=2),  # 쿨다운은 지남
                finished_at=_utc_now() - timedelta(hours=2),
                requester_ip="9.9.9.9",
            ))
        # hour window 안에는 3건 배치
        for t in ("005930", "000660", "035420"):
            db.add(GovernanceExtractRequest(
                ticker=t, status="done",
                requested_at=_utc_now() - timedelta(minutes=30),
                finished_at=_utc_now() - timedelta(minutes=29),
                requester_ip="9.9.9.9",
            ))
        await db.commit()
    # 다른 ticker로 시도하되 동일 IP 헤더
    r = await client.post(
        "/api/companies/373220/governance/extract",
        headers={"X-Forwarded-For": "9.9.9.9"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ip_limit"

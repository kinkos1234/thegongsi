import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Company, User, WatchListItem
from app.routers import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


async def _governance_only_task(ticker: str):
    """backfill_days=0 경로 — 기존 DB 공시에서 governance 만 추출."""
    try:
        from app.services.graph.extractor import extract_from_disclosures
        result = await extract_from_disclosures(ticker)
        logger.info(f"watchlist governance-only {ticker}: {result.get('status')}")
    except Exception as e:
        logger.warning(f"watchlist governance-only {ticker} failed: {e}")


async def _backfill_task(ticker: str, days: int, user_id: str | None = None):
    """watchlist 추가 시 백그라운드 실행 — backfill → calendar 스캔 → DD 메모.

    각 단계는 독립적으로 try/except — DART throttle/실패가 하위 단계를 막지 않음.
    """
    from app.services.collectors.dart import backfill_ticker
    corp_code = ""
    try:
        result = await backfill_ticker(ticker, days=days)
        logger.info(f"watchlist backfill {ticker}: {result}")
        corp_code = (result or {}).get("corp_code", "")
    except Exception as e:
        logger.warning(f"watchlist backfill {ticker} failed (continuing chain): {e}")

    # corp_code가 backfill에서 안 나왔으면 DB에서 직접 조회 — 나머지 체인 유지
    if not corp_code:
        try:
            from app.database import async_session
            async with async_session() as db:
                res = await db.execute(select(Company).where(Company.ticker == ticker))
                c = res.scalar_one_or_none()
                corp_code = (c.corp_code if c else "") or ""
        except Exception as e:
            logger.warning(f"watchlist {ticker} corp_code lookup failed: {e}")

    # (1) 권리락·배당락 이벤트 스캔 + 저장 (corp_code 있어야 함)
    if corp_code:
        try:
            import asyncpg
            import os
            from app.services.calendar.ex_dates import scan_ex_dates, upsert_events
            events = await scan_ex_dates([(ticker, corp_code)], days_back=180, concurrency=3)
            if events:
                url = os.environ.get("DATABASE_URL", "")
                for p in ("postgresql+asyncpg://", "postgres+asyncpg://"):
                    if url.startswith(p):
                        url = url.replace(p, "postgresql://", 1)
                        break
                conn = await asyncpg.connect(url)
                try:
                    await upsert_events(conn, events)
                    logger.info(f"watchlist calendar {ticker}: +{len(events)} events")
                finally:
                    await conn.close()
        except Exception as e:
            logger.warning(f"watchlist calendar {ticker} skipped: {e}")

    # (2) DD 메모 자동 생성 — DB 내 기존 공시/뉴스 기반. backfill 실패와 무관.
    try:
        from app.services.memo.generator import generate_memo
        memo_result = await generate_memo(ticker, user_id=user_id)
        logger.info(f"watchlist auto-memo {ticker}: version={memo_result.get('version')}")
    except Exception as e:
        logger.warning(f"watchlist auto-memo {ticker} skipped: {e}")

    # (3) governance 스냅샷 추출 — 최대주주·임원·법인지분. DART 본문에서 LLM 으로.
    # 별도 try/except — Anthropic 한도 / 공시 부족 시 조용히 패스.
    try:
        from app.services.graph.extractor import extract_from_disclosures
        gov_result = await extract_from_disclosures(ticker)
        logger.info(f"watchlist governance {ticker}: {gov_result.get('status')}")
    except Exception as e:
        logger.warning(f"watchlist governance {ticker} skipped: {e}")


class AddRequest(BaseModel):
    ticker: str
    backfill_days: int = Field(90, ge=0, le=365, description="공시 백필 기간 (0=비활성, 최대 1년)")


@router.get("/")
async def list_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Watchlist + Company.name_ko 병기 (LEFT JOIN, 이름 없으면 null)."""
    result = await db.execute(
        select(WatchListItem, Company.name_ko, Company.market)
        .outerjoin(Company, Company.ticker == WatchListItem.ticker)
        .where(WatchListItem.user_id == user.id)
        .order_by(WatchListItem.added_at.desc())
    )
    return [
        {
            "ticker": item.ticker,
            "name": name or None,
            "market": market or None,
            "added_at": item.added_at.isoformat(),
        }
        for item, name, market in result.all()
    ]


@router.post("/")
async def add_watchlist(
    req: AddRequest,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(WatchListItem).where(WatchListItem.user_id == user.id, WatchListItem.ticker == req.ticker)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 추가된 종목입니다.")
    item = WatchListItem(user_id=user.id, ticker=req.ticker)
    db.add(item)
    await db.commit()

    # 백그라운드: 최근 N일 공시 백필 + calendar + DD 메모 + governance 추출.
    # backfill_days=0 인 경우에도 governance 만큼은 단독 실행 (기존 DB 공시 기반).
    if req.backfill_days > 0:
        background.add_task(_backfill_task, req.ticker, req.backfill_days, user.id)
        backfill_status = f"queued_{req.backfill_days}d"
    else:
        background.add_task(_governance_only_task, req.ticker)
        backfill_status = "governance_only"

    return {"ticker": req.ticker, "status": "added", "backfill": backfill_status}


@router.delete("/{ticker}")
async def remove_watchlist(ticker: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WatchListItem).where(WatchListItem.user_id == user.id, WatchListItem.ticker == ticker)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="없는 종목입니다.")
    await db.delete(item)
    await db.commit()
    return {"status": "removed"}

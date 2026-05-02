import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tables import Company, Disclosure, EventReview, User, WatchListItem
from app.routers import get_current_user
from app.services.organizations import current_organization_id

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
            from app.services.calendar.ex_dates import scan_ex_dates
            from app.services.calendar.upsert import upsert_calendar_events
            events = await scan_ex_dates([(ticker, corp_code)], days_back=180, concurrency=3)
            if events:
                await upsert_calendar_events(events)
                logger.info(f"watchlist calendar {ticker}: +{len(events)} events")
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


@router.get("/brief")
async def watchlist_brief(
    days: int = 7,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """관심종목 기준 high/medium 공시 브리핑.

    제품의 1차 워크플로: "내 종목에서 오늘 무엇을 봐야 하나?"에 답한다.
    전시장 이벤트 큐와 달리 로그인 사용자의 watchlist tickers로 먼저 좁힌다.
    """
    days = max(1, min(30, days))
    limit = max(1, min(100, limit))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    watch_rows = (
        await db.execute(
            select(WatchListItem.ticker)
            .where(WatchListItem.user_id == user.id)
            .order_by(WatchListItem.added_at.desc())
        )
    ).all()
    tickers = [row[0] for row in watch_rows]
    if not tickers:
        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "watchlist_count": 0,
            "counts": {"high": 0, "med": 0, "new": 0, "reviewed": 0, "dismissed": 0, "escalated": 0},
            "items": [],
            "quiet_tickers": [],
        }

    severity_rank = case(
        (Disclosure.anomaly_severity == "high", 0),
        (Disclosure.anomaly_severity == "med", 1),
        else_=2,
    )
    rows = (
        await db.execute(
            select(Disclosure, Company.name_ko, Company.market, Company.sector)
            .join(Company, Company.ticker == Disclosure.ticker, isouter=True)
            .where(
                Disclosure.ticker.in_(tickers),
                Disclosure.rcept_dt >= cutoff,
                Disclosure.anomaly_severity.in_(["high", "med"]),
            )
            .order_by(severity_rank.asc(), Disclosure.rcept_dt.desc())
            .limit(limit)
        )
    ).all()

    review_map: dict[str, EventReview] = {}
    if rows:
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
    active_tickers: set[str] = set()
    for d, name, market, sector in rows:
        active_tickers.add(d.ticker)
        review = review_map.get(d.rcept_no)
        severity = d.anomaly_severity or "uncertain"
        items.append({
            "id": d.rcept_no,
            "ticker": d.ticker,
            "company": name,
            "market": market,
            "sector": sector,
            "date": d.rcept_dt,
            "title": d.report_nm,
            "severity": severity,
            "reason": d.anomaly_reason,
            "summary": d.summary_ko,
            "status": review.status if review else "new",
            "review_note": review.note if review else None,
            "evidence": {
                "rcept_no": d.rcept_no,
                "dart_url": d.raw_url or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.rcept_no}",
            },
        })

    quiet_tickers = [ticker for ticker in tickers if ticker not in active_tickers]
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
        "watchlist_count": len(tickers),
        "counts": counts,
        "items": items,
        "quiet_tickers": quiet_tickers,
    }


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

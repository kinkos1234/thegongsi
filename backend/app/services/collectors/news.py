"""뉴스 수집기 — RSS 기반.

소스: 네이버 뉴스 증권/산업 카테고리, 연합인포맥스 기업, 한경 증권.
DART 키 없어도 동작. 본문은 URL만 저장, 본문 스크래핑은 Phase 2.

watchlist에 등록된 티커별로 최근 뉴스 매칭 (제목 기반 단순 매칭).
"""
import logging
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.tables import Company, NewsItem, WatchListItem

logger = logging.getLogger(__name__)

# (RSS URL, source 라벨)
FEEDS = [
    ("https://www.yna.co.kr/rss/economy.xml", "연합뉴스 경제"),
    ("https://rss.hankyung.com/new/news_economy.xml", "한국경제 경제"),
    ("https://rss.hankyung.com/new/news_industry.xml", "한국경제 산업"),
]


def _parse_pub_date(s: str) -> datetime:
    # RFC 822 → datetime
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(s).replace(tzinfo=None)
    except Exception:
        return datetime.now(timezone.utc).replace(tzinfo=None)


async def _fetch_feed(url: str, source: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        logger.warning(f"RSS fetch failed {source}: {e}")
        return []

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = _parse_pub_date(item.findtext("pubDate") or "")
        if title and link:
            items.append({"title": title, "url": link, "source": source, "published_at": pub})
    return items


async def _match_tickers(db: AsyncSession, items: list[dict]) -> list[tuple[str, dict]]:
    """제목에 회사명(name_ko) 포함되면 해당 ticker로 매칭. 여러 매칭 가능."""
    # watchlist에 있는 회사만 매칭 (스팸 방지)
    wl_res = await db.execute(select(WatchListItem.ticker).distinct())
    tracked = {row[0] for row in wl_res.all()}
    if not tracked:
        return []

    companies_res = await db.execute(select(Company).where(Company.ticker.in_(tracked)))
    companies = companies_res.scalars().all()

    matches = []
    for item in items:
        for c in companies:
            if c.name_ko and c.name_ko in item["title"]:
                matches.append((c.ticker, item))
    return matches


async def fetch_news() -> dict:
    all_items = []
    for url, source in FEEDS:
        rows = await _fetch_feed(url, source)
        all_items.extend(rows)
    logger.info(f"RSS: {len(all_items)} items fetched")

    inserted = 0
    async with async_session() as db:
        matches = await _match_tickers(db, all_items)
        for ticker, item in matches:
            # URL 중복 체크
            exists = await db.execute(select(NewsItem).where(NewsItem.url == item["url"], NewsItem.ticker == ticker))
            if exists.scalar_one_or_none():
                continue
            db.add(NewsItem(
                ticker=ticker,
                title=item["title"],
                source=item["source"],
                url=item["url"],
                published_at=item["published_at"],
            ))
            inserted += 1
        await db.commit()

    logger.info(f"News: {inserted} inserted (matched {len(matches)})")
    return {"fetched": len(all_items), "matched": len(matches), "inserted": inserted}

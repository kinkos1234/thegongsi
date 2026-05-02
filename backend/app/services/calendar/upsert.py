"""Calendar event persistence helpers."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import async_session, engine
from app.models.tables import CalendarEvent


async def upsert_calendar_events(events: Sequence[dict]) -> int:
    """Upsert calendar events through SQLAlchemy for local SQLite and Postgres."""
    if not events:
        return 0

    insert_fn = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    rows = [
        {
            "id": e["id"],
            "ticker": e["ticker"],
            "event_type": e["event_type"],
            "event_date": e["event_date"],
            "rcept_no": e["rcept_no"],
            "title": e.get("title"),
            "notes": e.get("notes"),
            "fetched_at": e["fetched_at"],
        }
        for e in events
    ]
    stmt = insert_fn(CalendarEvent).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "event_type", "event_date", "rcept_no"],
        set_={
            "title": stmt.excluded.title,
            "notes": stmt.excluded.notes,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    async with async_session() as session:
        await session.execute(stmt)
        await session.commit()
    return len(rows)

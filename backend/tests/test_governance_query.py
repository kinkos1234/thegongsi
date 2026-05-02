from app.services.graph.governance_query import _dedupe_linked


def test_dedupe_linked_keeps_strongest_stake_for_same_name():
    rows = [
        {"ticker": "000830", "name": "삼성물산", "stake_pct": 4.49, "as_of": "2026-04-19"},
        {"ticker": "028260", "name": "삼성물산", "stake_pct": 5.11, "as_of": "2026-04-19"},
        {"ticker": "032830", "name": "삼성생명", "stake_pct": 7.49, "as_of": "2026-04-19"},
    ]

    deduped = _dedupe_linked(rows)

    assert [r["ticker"] for r in deduped] == ["032830", "028260"]

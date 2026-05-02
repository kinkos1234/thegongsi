"""organization workspaces

Revision ID: 20260502_0002
Revises: 20260502_0001
Create Date: 2026-05-02 01:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models.tables import Base

revision = "20260502_0002"
down_revision = "20260502_0001"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {col["name"] for col in _inspector().get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

    user_cols = _columns("users")
    if "default_organization_id" not in user_cols:
        op.add_column("users", sa.Column("default_organization_id", sa.String(length=12), nullable=True))
    if not _index_exists("users", "ix_users_default_organization_id"):
        op.create_index("ix_users_default_organization_id", "users", ["default_organization_id"])

    review_cols = _columns("event_reviews")
    if "organization_id" not in review_cols:
        op.add_column("event_reviews", sa.Column("organization_id", sa.String(length=12), nullable=True))
    if "reviewed_by_user_id" not in review_cols:
        op.add_column("event_reviews", sa.Column("reviewed_by_user_id", sa.String(length=12), nullable=True))
    if not _index_exists("event_reviews", "ix_event_reviews_organization_id"):
        op.create_index("ix_event_reviews_organization_id", "event_reviews", ["organization_id"])
    if not _index_exists("event_reviews", "ix_event_reviews_reviewed_by_user_id"):
        op.create_index("ix_event_reviews_reviewed_by_user_id", "event_reviews", ["reviewed_by_user_id"])


def downgrade() -> None:
    # SQLite cannot drop columns without batch table rebuild. Keep downgrade
    # conservative; later production migrations should be forward-only unless
    # a tested data migration is provided.
    if _table_exists("organization_members"):
        op.drop_table("organization_members")
    if _table_exists("organizations"):
        op.drop_table("organizations")

"""organization invitations

Revision ID: 20260502_0003
Revises: 20260502_0002
Create Date: 2026-05-02 02:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models.tables import Base

revision = "20260502_0003"
down_revision = "20260502_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "organization_invites" in sa.inspect(bind).get_table_names():
        op.drop_table("organization_invites")

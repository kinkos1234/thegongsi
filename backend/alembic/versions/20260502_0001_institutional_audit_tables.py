"""institutional audit and evidence tables

Revision ID: 20260502_0001
Revises:
Create Date: 2026-05-02 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.models.tables import Base

revision = "20260502_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Baseline migration: fresh databases receive the full current schema, while
    # existing production databases only get tables that are still missing.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

    if not _table_exists("event_reviews"):
        op.create_table(
            "event_reviews",
            sa.Column("id", sa.String(length=12), nullable=False),
            sa.Column("user_id", sa.String(length=12), nullable=False),
            sa.Column("rcept_no", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "rcept_no", name="uq_event_review_user_event"),
        )
        op.create_index(op.f("ix_event_reviews_user_id"), "event_reviews", ["user_id"])
        op.create_index(op.f("ix_event_reviews_rcept_no"), "event_reviews", ["rcept_no"])

    if not _table_exists("admin_job_runs"):
        op.create_table(
            "admin_job_runs",
            sa.Column("id", sa.String(length=12), nullable=False),
            sa.Column("job_id", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("triggered_by", sa.String(length=40), nullable=False),
            sa.Column("params_json", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("elapsed_seconds", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_admin_job_runs_job_id"), "admin_job_runs", ["job_id"])
        op.create_index(op.f("ix_admin_job_runs_status"), "admin_job_runs", ["status"])
        op.create_index(op.f("ix_admin_job_runs_started_at"), "admin_job_runs", ["started_at"])

    if not _table_exists("disclosure_evidence"):
        op.create_table(
            "disclosure_evidence",
            sa.Column("id", sa.String(length=12), nullable=False),
            sa.Column("rcept_no", sa.String(length=20), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("method", sa.String(length=32), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("model", sa.String(length=80), nullable=True),
            sa.Column("prompt_version", sa.String(length=40), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("rcept_no", "kind", name="uq_disclosure_evidence_kind"),
        )
        op.create_index(op.f("ix_disclosure_evidence_rcept_no"), "disclosure_evidence", ["rcept_no"])
        op.create_index(op.f("ix_disclosure_evidence_kind"), "disclosure_evidence", ["kind"])


def downgrade() -> None:
    if _table_exists("disclosure_evidence"):
        op.drop_table("disclosure_evidence")
    if _table_exists("admin_job_runs"):
        op.drop_table("admin_job_runs")
    if _table_exists("event_reviews"):
        op.drop_table("event_reviews")

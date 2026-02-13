"""initial schema

Revision ID: 20260214_0001
Revises: 
Create Date: 2026-02-14 00:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260214_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instrument",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_key", sa.String(length=64), nullable=False),
        sa.Column("name_sv", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=64), nullable=False),
        sa.Column("module", sa.String(length=32), nullable=False),
        sa.Column("unit_label", sa.String(length=64), nullable=True),
        sa.Column("price_type", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_instrument_instrument_key", "instrument", ["instrument_key"], unique=True)
    op.create_index("ix_instrument_module", "instrument", ["module"], unique=False)
    op.create_index("ix_instrument_ticker", "instrument", ["ticker"], unique=False)

    op.create_table(
        "quote_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instrument.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last", sa.Float(), nullable=True),
        sa.Column("day_abs", sa.Float(), nullable=True),
        sa.Column("day_pct", sa.Float(), nullable=True),
        sa.Column("w1_pct", sa.Float(), nullable=True),
        sa.Column("ytd_pct", sa.Float(), nullable=True),
        sa.Column("y1_pct", sa.Float(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_quote_snapshot_fetched_at", "quote_snapshot", ["fetched_at"], unique=False)
    op.create_index("ix_quote_snapshot_instrument_id", "quote_snapshot", ["instrument_id"], unique=False)

    op.create_table(
        "series_point",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instrument.id", ondelete="CASCADE"), nullable=False),
        sa.Column("series_type", sa.String(length=32), nullable=False),
        sa.Column("range_key", sa.String(length=16), nullable=False),
        sa.Column("point_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("instrument_id", "series_type", "range_key", "point_time", name="uq_series_point"),
    )
    op.create_index("ix_series_point_fetched_at", "series_point", ["fetched_at"], unique=False)
    op.create_index("ix_series_point_instrument_id", "series_point", ["instrument_id"], unique=False)
    op.create_index("ix_series_point_point_time", "series_point", ["point_time"], unique=False)
    op.create_index("ix_series_point_range_key", "series_point", ["range_key"], unique=False)
    op.create_index("ix_series_point_series_type", "series_point", ["series_type"], unique=False)

    op.create_table(
        "job_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ok_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_job_run_job_name", "job_run", ["job_name"], unique=False)
    op.create_index("ix_job_run_started_at", "job_run", ["started_at"], unique=False)
    op.create_index("ix_job_run_status", "job_run", ["status"], unique=False)

    op.create_table(
        "provider_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_event_created_at", "provider_event", ["created_at"], unique=False)
    op.create_index("ix_provider_event_event_type", "provider_event", ["event_type"], unique=False)
    op.create_index("ix_provider_event_provider", "provider_event", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_provider_event_provider", table_name="provider_event")
    op.drop_index("ix_provider_event_event_type", table_name="provider_event")
    op.drop_index("ix_provider_event_created_at", table_name="provider_event")
    op.drop_table("provider_event")

    op.drop_index("ix_job_run_status", table_name="job_run")
    op.drop_index("ix_job_run_started_at", table_name="job_run")
    op.drop_index("ix_job_run_job_name", table_name="job_run")
    op.drop_table("job_run")

    op.drop_index("ix_series_point_series_type", table_name="series_point")
    op.drop_index("ix_series_point_range_key", table_name="series_point")
    op.drop_index("ix_series_point_point_time", table_name="series_point")
    op.drop_index("ix_series_point_instrument_id", table_name="series_point")
    op.drop_index("ix_series_point_fetched_at", table_name="series_point")
    op.drop_table("series_point")

    op.drop_index("ix_quote_snapshot_instrument_id", table_name="quote_snapshot")
    op.drop_index("ix_quote_snapshot_fetched_at", table_name="quote_snapshot")
    op.drop_table("quote_snapshot")

    op.drop_index("ix_instrument_ticker", table_name="instrument")
    op.drop_index("ix_instrument_module", table_name="instrument")
    op.drop_index("ix_instrument_instrument_key", table_name="instrument")
    op.drop_table("instrument")

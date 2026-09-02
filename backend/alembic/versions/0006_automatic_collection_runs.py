"""Persist automatic collection runs and regional work.

Revision ID: 0006_automatic_collection_runs
Revises: 0005_national_multiregion_sessions
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_automatic_collection_runs"
down_revision: str | None = "0005_national_multiregion_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_session_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("candidate_source", sa.String(32), nullable=False, server_default="browser"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_region_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_region_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_region_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_region_code", sa.String(12), nullable=True),
        sa.Column("pause_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["search_session_id"], ["search_sessions.id"]),
        sa.UniqueConstraint(
            "search_session_id",
            "platform",
            name="uq_collection_run_session_platform",
        ),
    )
    op.create_index("ix_collection_runs_search_session_id", "collection_runs", ["search_session_id"])
    op.create_index("ix_collection_runs_status", "collection_runs", ["status"])

    op.create_table(
        "collection_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_run_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("platform_sku_id", sa.String(160), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("platform_shop_id", sa.String(160), nullable=True),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("shop_type", sa.String(40), nullable=False),
        sa.Column("initial_price_cents", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["collection_run_id"], ["collection_runs.id"]),
        sa.UniqueConstraint(
            "collection_run_id",
            "platform_sku_id",
            name="uq_collection_candidate_sku",
        ),
    )
    op.create_index(
        "ix_collection_candidates_collection_run_id",
        "collection_candidates",
        ["collection_run_id"],
    )

    op.create_table(
        "collection_region_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_run_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(12), nullable=False),
        sa.Column("province", sa.String(80), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("district", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_offer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["collection_run_id"], ["collection_runs.id"]),
        sa.UniqueConstraint(
            "collection_run_id",
            "region_code",
            name="uq_collection_task_region",
        ),
    )
    op.create_index(
        "ix_collection_region_tasks_collection_run_id",
        "collection_region_tasks",
        ["collection_run_id"],
    )
    op.create_index("ix_collection_region_tasks_status", "collection_region_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_collection_region_tasks_status", table_name="collection_region_tasks")
    op.drop_index(
        "ix_collection_region_tasks_collection_run_id",
        table_name="collection_region_tasks",
    )
    op.drop_table("collection_region_tasks")
    op.drop_index(
        "ix_collection_candidates_collection_run_id",
        table_name="collection_candidates",
    )
    op.drop_table("collection_candidates")
    op.drop_index("ix_collection_runs_status", table_name="collection_runs")
    op.drop_index("ix_collection_runs_search_session_id", table_name="collection_runs")
    op.drop_table("collection_runs")

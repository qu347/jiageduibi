"""Persist OCR price sheet batches and regional results.

Revision ID: 0008_price_sheet_batches
Revises: 0007_collection_region_streets
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0008_price_sheet_batches"
down_revision: str | None = "0007_collection_region_streets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_sheet_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("date_inferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("recognized_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lower_price_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_item_id", sa.Integer(), nullable=True),
        sa.Column("pause_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_price_sheet_batches_status", "price_sheet_batches", ["status"])

    op.create_table(
        "price_sheet_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("brand", sa.String(80), nullable=False),
        sa.Column("model_name", sa.String(160), nullable=False),
        sa.Column("storage", sa.String(40), nullable=False),
        sa.Column("color", sa.String(80), nullable=False),
        sa.Column("today_price_cents", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("candidates_json", sa.Text(), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_region_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_region_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_region_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lowest_price_cents", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["price_sheet_batches.id"]),
        sa.UniqueConstraint(
            "batch_id", "model_name", "storage", "color",
            name="uq_price_sheet_item_variant",
        ),
    )
    op.create_index("ix_price_sheet_items_batch_id", "price_sheet_items", ["batch_id"])
    op.create_index("ix_price_sheet_items_status", "price_sheet_items", ["status"])

    op.create_table(
        "price_sheet_region_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("price_sheet_item_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(12), nullable=False),
        sa.Column("province", sa.String(80), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("district", sa.String(80), nullable=False),
        sa.Column("street", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lowest_result_cents", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["price_sheet_item_id"], ["price_sheet_items.id"]),
        sa.UniqueConstraint(
            "price_sheet_item_id", "region_code", name="uq_price_sheet_task_region",
        ),
    )
    op.create_index(
        "ix_price_sheet_region_tasks_price_sheet_item_id",
        "price_sheet_region_tasks", ["price_sheet_item_id"],
    )
    op.create_index("ix_price_sheet_region_tasks_status", "price_sheet_region_tasks", ["status"])

    op.create_table(
        "price_sheet_region_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("price_sheet_item_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(12), nullable=False),
        sa.Column("platform_sku_id", sa.String(160), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("shop_type", sa.String(40), nullable=False),
        sa.Column("listed_price_cents", sa.Integer(), nullable=True),
        sa.Column("sale_price_cents", sa.Integer(), nullable=False),
        sa.Column("merchant_discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_coupon_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subsidy_amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shipping_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trusted_price_cents", sa.Integer(), nullable=False),
        sa.Column("sale_price_includes_coupon", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sale_price_includes_subsidy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stock_status", sa.String(40), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["price_sheet_item_id"], ["price_sheet_items.id"]),
        sa.UniqueConstraint(
            "price_sheet_item_id", "region_code", name="uq_price_sheet_result_region",
        ),
    )
    op.create_index(
        "ix_price_sheet_region_results_price_sheet_item_id",
        "price_sheet_region_results", ["price_sheet_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_price_sheet_region_results_price_sheet_item_id",
        table_name="price_sheet_region_results",
    )
    op.drop_table("price_sheet_region_results")
    op.drop_index("ix_price_sheet_region_tasks_status", table_name="price_sheet_region_tasks")
    op.drop_index(
        "ix_price_sheet_region_tasks_price_sheet_item_id",
        table_name="price_sheet_region_tasks",
    )
    op.drop_table("price_sheet_region_tasks")
    op.drop_index("ix_price_sheet_items_status", table_name="price_sheet_items")
    op.drop_index("ix_price_sheet_items_batch_id", table_name="price_sheet_items")
    op.drop_table("price_sheet_items")
    op.drop_index("ix_price_sheet_batches_status", table_name="price_sheet_batches")
    op.drop_table("price_sheet_batches")

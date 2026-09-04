"""Persist guarded JD checkout preview tasks and results.

Revision ID: 0009_jd_checkout_previews
Revises: 0008_price_sheet_batches
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009_jd_checkout_previews"
down_revision: str | None = "0008_price_sheet_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_sheet_checkout_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("price_sheet_item_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(12), nullable=False),
        sa.Column("platform_sku_id", sa.String(160), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("entry_mode", sa.String(32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["price_sheet_item_id"], ["price_sheet_items.id"]),
        sa.UniqueConstraint(
            "price_sheet_item_id", "region_code", "platform_sku_id",
            name="uq_price_sheet_checkout_item_region_sku",
        ),
    )
    op.create_index(
        "ix_price_sheet_checkout_tasks_price_sheet_item_id",
        "price_sheet_checkout_tasks", ["price_sheet_item_id"],
    )
    op.create_index("ix_price_sheet_checkout_tasks_region_code", "price_sheet_checkout_tasks", ["region_code"])
    op.create_index("ix_price_sheet_checkout_tasks_status", "price_sheet_checkout_tasks", ["status"])

    op.create_table(
        "price_sheet_checkout_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checkout_task_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("shop_type", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("line_original_price_cents", sa.Integer(), nullable=True),
        sa.Column("line_sale_price_cents", sa.Integer(), nullable=True),
        sa.Column("merchant_discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ordinary_coupon_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subsidy_amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shipping_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payable_price_cents", sa.Integer(), nullable=True),
        sa.Column("discount_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("conditional_reason", sa.Text(), nullable=True),
        sa.Column("unavailable_code", sa.String(64), nullable=True),
        sa.Column("price_status", sa.String(32), nullable=False),
        sa.Column("region_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cart_restored", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["checkout_task_id"], ["price_sheet_checkout_tasks.id"]),
        sa.UniqueConstraint("checkout_task_id", name="uq_price_sheet_checkout_result_task"),
    )
    op.create_index(
        "ix_price_sheet_checkout_results_checkout_task_id",
        "price_sheet_checkout_results", ["checkout_task_id"],
    )
    op.create_index(
        "ix_price_sheet_checkout_results_price_status",
        "price_sheet_checkout_results", ["price_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_sheet_checkout_results_price_status", table_name="price_sheet_checkout_results")
    op.drop_index("ix_price_sheet_checkout_results_checkout_task_id", table_name="price_sheet_checkout_results")
    op.drop_table("price_sheet_checkout_results")
    op.drop_index("ix_price_sheet_checkout_tasks_status", table_name="price_sheet_checkout_tasks")
    op.drop_index("ix_price_sheet_checkout_tasks_region_code", table_name="price_sheet_checkout_tasks")
    op.drop_index("ix_price_sheet_checkout_tasks_price_sheet_item_id", table_name="price_sheet_checkout_tasks")
    op.drop_table("price_sheet_checkout_tasks")

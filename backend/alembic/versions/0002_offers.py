"""Create search, offer, snapshot, and adapter-run tables.

Revision ID: 0002_offers
Revises: 0001_catalog
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002_offers"
down_revision: str | None = "0001_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platforms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_platforms_code"),
    )
    op.create_table(
        "shops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("platform_shop_id", sa.String(160), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("shop_type", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"]),
        sa.UniqueConstraint("platform_id", "platform_shop_id", name="uq_shops_platform_shop"),
    )
    op.create_index("ix_shops_platform_id", "shops", ["platform_id"])
    op.create_table(
        "platform_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=True),
        sa.Column("platform_product_id", sa.String(160), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.String(80), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"]),
        sa.UniqueConstraint("platform_id", "platform_product_id", name="uq_platform_products_identity"),
    )
    op.create_index("ix_platform_products_platform_id", "platform_products", ["platform_id"])
    op.create_table(
        "search_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("region_code", sa.String(12), nullable=True),
        sa.Column("include_conditional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="collecting"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
    )
    op.create_index("ix_search_sessions_variant_id", "search_sessions", ["variant_id"])
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_session_id", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("platform_product_id", sa.Integer(), nullable=True),
        sa.Column("shop_id", sa.Integer(), nullable=True),
        sa.Column("platform_sku_id", sa.String(160), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(80), nullable=True),
        sa.Column("model_name", sa.String(160), nullable=True),
        sa.Column("model_code", sa.String(120), nullable=True),
        sa.Column("storage", sa.String(32), nullable=True),
        sa.Column("memory", sa.String(32), nullable=True),
        sa.Column("color", sa.String(80), nullable=True),
        sa.Column("region_version", sa.String(80), nullable=True),
        sa.Column("condition", sa.String(32), nullable=True),
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("listed_price_cents", sa.Integer(), nullable=True),
        sa.Column("sale_price_cents", sa.Integer(), nullable=True),
        sa.Column("merchant_discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_coupon_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("member_discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payment_discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subsidy_amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shipping_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("installation_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_price_cents", sa.Integer(), nullable=True),
        sa.Column("estimated_final_price_cents", sa.Integer(), nullable=True),
        sa.Column("comparable_price_cents", sa.Integer(), nullable=True),
        sa.Column("conditional_price_cents", sa.Integer(), nullable=True),
        sa.Column("price_type", sa.String(32), nullable=False, server_default="total"),
        sa.Column("price_conditions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("stock_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("excluded_reason", sa.String(80), nullable=True),
        sa.Column("subsidy_status", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("region_code", sa.String(12), nullable=True),
        sa.Column("match_confidence", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("adapter_version", sa.String(80), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["search_session_id"], ["search_sessions.id"]),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"]),
        sa.ForeignKeyConstraint(["platform_product_id"], ["platform_products.id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"]),
        sa.UniqueConstraint(
            "search_session_id",
            "platform_id",
            "platform_sku_id",
            name="uq_offers_session_platform_sku",
        ),
    )
    op.create_index("ix_offers_search_session_id", "offers", ["search_session_id"])
    op.create_index("ix_offers_platform_id", "offers", ["platform_id"])
    op.create_table(
        "price_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("component_type", sa.String(40), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("condition_code", sa.String(80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
    )
    op.create_index("ix_price_components_offer_id", "price_components", ["offer_id"])
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("comparable_price_cents", sa.Integer(), nullable=True),
        sa.Column("estimated_final_price_cents", sa.Integer(), nullable=True),
        sa.Column("subsidy_status", sa.String(24), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
    )
    op.create_index("ix_price_snapshots_offer_id", "price_snapshots", ["offer_id"])
    op.create_table(
        "offer_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("excluded_reason", sa.String(80), nullable=True),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
    )
    op.create_index("ix_offer_matches_offer_id", "offer_matches", ["offer_id"])
    op.create_table(
        "manual_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(80), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
    )
    op.create_index("ix_manual_corrections_offer_id", "manual_corrections", ["offer_id"])
    op.create_table(
        "adapter_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("adapter_version", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"]),
    )
    op.create_index("ix_adapter_runs_platform_id", "adapter_runs", ["platform_id"])


def downgrade() -> None:
    op.drop_index("ix_adapter_runs_platform_id", table_name="adapter_runs")
    op.drop_table("adapter_runs")
    op.drop_index("ix_manual_corrections_offer_id", table_name="manual_corrections")
    op.drop_table("manual_corrections")
    op.drop_index("ix_offer_matches_offer_id", table_name="offer_matches")
    op.drop_table("offer_matches")
    op.drop_index("ix_price_snapshots_offer_id", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    op.drop_index("ix_price_components_offer_id", table_name="price_components")
    op.drop_table("price_components")
    op.drop_index("ix_offers_platform_id", table_name="offers")
    op.drop_index("ix_offers_search_session_id", table_name="offers")
    op.drop_table("offers")
    op.drop_index("ix_search_sessions_variant_id", table_name="search_sessions")
    op.drop_table("search_sessions")
    op.drop_index("ix_platform_products_platform_id", table_name="platform_products")
    op.drop_table("platform_products")
    op.drop_index("ix_shops_platform_id", table_name="shops")
    op.drop_table("shops")
    op.drop_table("platforms")

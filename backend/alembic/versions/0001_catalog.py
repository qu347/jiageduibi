"""Create the standard product catalog.

Revision ID: 0001_catalog
Revises:
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0001_catalog"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_brands_name"),
    )
    op.create_table(
        "product_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.UniqueConstraint("brand_id", "name", name="uq_product_series_brand_name"),
    )
    op.create_index("ix_product_series_brand_id", "product_series", ["brand_id"])
    op.create_table(
        "product_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("model_code", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["series_id"], ["product_series.id"]),
        sa.UniqueConstraint("series_id", "model_name", name="uq_product_models_series_name"),
        sa.UniqueConstraint("model_code", name="uq_product_models_model_code"),
    )
    op.create_index("ix_product_models_series_id", "product_models", ["series_id"])
    op.create_index("ix_product_models_model_code", "product_models", ["model_code"])
    op.create_index("ix_product_models_category", "product_models", ["category"])
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("sku_code", sa.String(length=120), nullable=False),
        sa.Column("storage", sa.String(length=32), nullable=False),
        sa.Column("memory", sa.String(length=32), nullable=True),
        sa.Column("color", sa.String(length=80), nullable=False),
        sa.Column("region_version", sa.String(length=80), nullable=False),
        sa.Column("condition", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"]),
        sa.UniqueConstraint("sku_code", name="uq_product_variants_sku_code"),
        sa.UniqueConstraint(
            "model_id",
            "storage",
            "memory",
            "color",
            "region_version",
            "condition",
            name="uq_product_variants_identity",
        ),
    )
    op.create_index("ix_product_variants_model_id", "product_variants", ["model_id"])
    op.create_index("ix_product_variants_sku_code", "product_variants", ["sku_code"])
    op.create_table(
        "product_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=180), nullable=False),
        sa.Column("normalized_alias", sa.String(length=180), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"]),
        sa.UniqueConstraint("model_id", "normalized_alias", name="uq_product_aliases_model_alias"),
    )
    op.create_index("ix_product_aliases_model_id", "product_aliases", ["model_id"])
    op.create_index("ix_product_aliases_normalized_alias", "product_aliases", ["normalized_alias"])


def downgrade() -> None:
    op.drop_index("ix_product_aliases_normalized_alias", table_name="product_aliases")
    op.drop_index("ix_product_aliases_model_id", table_name="product_aliases")
    op.drop_table("product_aliases")
    op.drop_index("ix_product_variants_sku_code", table_name="product_variants")
    op.drop_index("ix_product_variants_model_id", table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_index("ix_product_models_category", table_name="product_models")
    op.drop_index("ix_product_models_model_code", table_name="product_models")
    op.drop_index("ix_product_models_series_id", table_name="product_models")
    op.drop_table("product_models")
    op.drop_index("ix_product_series_brand_id", table_name="product_series")
    op.drop_table("product_series")
    op.drop_table("brands")

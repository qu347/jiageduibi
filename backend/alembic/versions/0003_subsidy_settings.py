"""Create subsidy rules and local settings tables.

Revision ID: 0003_subsidy_settings
Revises: 0002_offers
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_subsidy_settings"
down_revision: str | None = "0002_offers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subsidy_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_code", sa.String(12), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("max_unit_price_cents", sa.Integer(), nullable=True),
        sa.Column("subsidy_rate_basis_points", sa.Integer(), nullable=False),
        sa.Column("subsidy_cap_cents", sa.Integer(), nullable=True),
        sa.Column("participating_platforms_json", sa.Text(), nullable=False),
        sa.Column("participating_shop_types_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subsidy_rules_region_code", "subsidy_rules", ["region_code"])
    op.create_index("ix_subsidy_rules_category", "subsidy_rules", ["category"])
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", name="uq_app_settings_key"),
    )
    op.create_table(
        "backups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("backups")
    op.drop_table("app_settings")
    op.drop_index("ix_subsidy_rules_category", table_name="subsidy_rules")
    op.drop_index("ix_subsidy_rules_region_code", table_name="subsidy_rules")
    op.drop_table("subsidy_rules")

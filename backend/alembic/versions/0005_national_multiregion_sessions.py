"""Add comparison scope and per-region offer identity.

Revision ID: 0005_national_multiregion_sessions
Revises: 0004_offer_regions
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_national_multiregion_sessions"
down_revision: str | None = "0004_offer_regions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_region_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _region_key(region_code: str | None, region_name: str | None) -> str:
    if region_code:
        return f"code:{region_code.strip()}"
    if region_name:
        normalized_name = _normalize_region_name(region_name)
        if normalized_name in {"全国", "nationwide", "national"}:
            return "national"
        return f"name:{normalized_name}"
    return "unknown"


def upgrade() -> None:
    op.add_column("search_sessions", sa.Column("comparison_scope", sa.String(16), nullable=True))
    op.add_column("offers", sa.Column("region_key", sa.String(180), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE search_sessions
            SET comparison_scope = CASE
                WHEN region_code IS NULL THEN 'national'
                ELSE 'regional'
            END
            """
        )
    )
    rows = connection.execute(sa.text("SELECT id, region_code, region_name FROM offers")).mappings()
    for row in rows:
        connection.execute(
            sa.text("UPDATE offers SET region_key = :region_key WHERE id = :offer_id"),
            {"region_key": _region_key(row["region_code"], row["region_name"]), "offer_id": row["id"]},
        )

    with op.batch_alter_table("search_sessions") as batch_op:
        batch_op.alter_column(
            "comparison_scope",
            existing_type=sa.String(16),
            nullable=False,
        )
    with op.batch_alter_table("offers") as batch_op:
        batch_op.alter_column(
            "region_key",
            existing_type=sa.String(180),
            nullable=False,
            server_default="unknown",
        )
        batch_op.drop_constraint("uq_offers_session_platform_sku", type_="unique")
        batch_op.create_unique_constraint(
            "uq_offers_session_platform_sku_region",
            ["search_session_id", "platform_id", "platform_sku_id", "region_key"],
        )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text(
            """
            SELECT search_session_id, platform_id, platform_sku_id
            FROM offers
            GROUP BY search_session_id, platform_id, platform_sku_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError("存在跨地区重复报价，无法安全降级到单地区唯一约束")

    with op.batch_alter_table("offers") as batch_op:
        batch_op.drop_constraint("uq_offers_session_platform_sku_region", type_="unique")
        batch_op.create_unique_constraint(
            "uq_offers_session_platform_sku",
            ["search_session_id", "platform_id", "platform_sku_id"],
        )
        batch_op.drop_column("region_key")
    with op.batch_alter_table("search_sessions") as batch_op:
        batch_op.drop_column("comparison_scope")

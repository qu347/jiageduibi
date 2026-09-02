"""Store the human-readable applicable region for each offer.

Revision ID: 0004_offer_regions
Revises: 0003_subsidy_settings
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_offer_regions"
down_revision: str | None = "0003_subsidy_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("region_name", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "region_name")

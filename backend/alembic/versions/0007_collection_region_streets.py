"""Persist representative street names for automatic collection.

Revision ID: 0007_collection_region_streets
Revises: 0006_automatic_collection_runs
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007_collection_region_streets"
down_revision: str | None = "0006_automatic_collection_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


STREETS = {
    "110100": "奥运村街道",
    "120100": "劝业场街道",
    "130100": "建北街道",
    "140100": "坞城街道",
    "150100": "中山东路街道",
    "210100": "五里河街道",
    "220100": "红旗街道",
    "230100": "花园街道",
    "310100": "陆家嘴街道",
    "320100": "新街口街道",
    "330100": "湖滨街道",
    "340100": "三里庵街道",
    "350100": "东街街道",
    "360100": "百花洲街道",
    "370100": "泉城路街道",
    "410100": "花园路街道",
    "420100": "中南路街道",
    "430100": "定王台街道",
    "440100": "天河南街道",
    "450100": "新竹街道",
    "460100": "金贸街道",
    "500100": "解放碑街道",
    "510100": "春熙路街道",
    "520100": "中华南路街道",
    "530100": "护国街道",
    "540100": "八廓街道",
    "610100": "小寨路街道",
    "620100": "张掖路街道",
    "630100": "西关大街街道",
    "640100": "解放西街街道",
    "650100": "解放南路街道",
}


def upgrade() -> None:
    connection = op.get_bind()
    unknown = connection.execute(sa.text("""
        SELECT DISTINCT region_code
        FROM collection_region_tasks
        WHERE region_code NOT IN :codes
        ORDER BY region_code
    """).bindparams(sa.bindparam("codes", expanding=True)), {"codes": tuple(STREETS)}).scalars().all()
    if unknown:
        raise RuntimeError(f"存在无法回填街道的地区任务: {', '.join(unknown)}")

    op.add_column("collection_region_tasks", sa.Column("street", sa.String(80), nullable=True))
    for region_code, street in STREETS.items():
        connection.execute(
            sa.text("""
                UPDATE collection_region_tasks
                SET street = :street
                WHERE region_code = :region_code
            """),
            {"region_code": region_code, "street": street},
        )
    with op.batch_alter_table("collection_region_tasks") as batch_op:
        batch_op.alter_column("street", existing_type=sa.String(80), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("collection_region_tasks") as batch_op:
        batch_op.drop_column("street")

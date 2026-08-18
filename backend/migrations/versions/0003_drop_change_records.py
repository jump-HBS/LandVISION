# -*- coding: utf-8 -*-
"""0003：删除变化监测表（变化监测模块已从项目中移除）。

Revision ID: 0003_drop_change_records
Revises: 0002_parcel_period
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0003_drop_change_records"
down_revision = "0002_parcel_period"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("change_records")


def downgrade() -> None:
    # 还原：与 0001_initial 中 change_records 定义一致
    op.create_table(
        "change_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("parcel_code", sa.String(50), nullable=True),
        sa.Column("change_type", sa.String(50), nullable=False),
        sa.Column("area_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("detected_date", sa.Date, nullable=True),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
    )

# -*- coding: utf-8 -*-
"""0002：地块表增加期次字段（支持两期用地转移矩阵分析）。

Revision ID: 0002_parcel_period
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_parcel_period"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parcels", sa.Column("period", sa.String(10), nullable=True))
    op.create_index("idx_parcels_period", "parcels", ["period"])


def downgrade() -> None:
    op.drop_index("idx_parcels_period", table_name="parcels")
    op.drop_column("parcels", "period")

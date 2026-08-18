# -*- coding: utf-8 -*-
"""初始迁移：五张业务表 + PostGIS 扩展 + 空间索引。

与 database/01_init_schema.sql 等价；从此以后表结构变更一律走 Alembic：
  alembic revision --autogenerate -m "xxx"  →  alembic upgrade head

注意：Geometry 字段声明后，GeoAlchemy2 的 alembic_helpers 会自动创建
GIST 空间索引（idx_<表名>_geom），无需手工 create_index。
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostGIS 扩展（数据库级，迁移中显式声明）
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "parcels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parcel_code", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("land_use", sa.String(50), nullable=False),
        sa.Column("district", sa.String(50)),
        sa.Column("region_code", sa.String(20)),
        sa.Column("area_sqm", sa.Numeric(14, 2)),
        sa.Column("far_limit", sa.Numeric(6, 2)),
        sa.Column("height_limit", sa.Numeric(6, 2)),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "pois",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("poi_type", sa.String(50), nullable=False),
        sa.Column("geom", Geometry("POINT", srid=4326), nullable=False),
    )

    op.create_table(
        "planning_control",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zone_name", sa.String(100), nullable=False),
        sa.Column("zone_type", sa.String(50), nullable=False),
        sa.Column("zone_level", sa.String(20)),
        sa.Column("control_desc", sa.Text()),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
    )

    op.create_table(
        "change_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parcel_code", sa.String(50)),
        sa.Column("change_type", sa.String(50), nullable=False),
        sa.Column("area_sqm", sa.Numeric(14, 2)),
        sa.Column("confidence", sa.Numeric(5, 2)),
        sa.Column("detected_date", sa.Date()),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
    )

    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("parent_code", sa.String(20)),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("regions")
    op.drop_table("change_records")
    op.drop_table("planning_control")
    op.drop_table("pois")
    op.drop_table("parcels")

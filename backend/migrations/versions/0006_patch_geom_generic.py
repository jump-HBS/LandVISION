# -*- coding: utf-8 -*-
"""0006：land_change_patches.geom 类型放宽为 GEOMETRY（消失/新增图斑可能为 MultiPolygon）。

Revision ID: 0006_patch_geom_generic
Revises: 0005_standardize_zone_types
"""
from alembic import op

revision = "0006_patch_geom_generic"
down_revision = "0005_standardize_zone_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE land_change_patches "
        "ALTER COLUMN geom TYPE geometry(Geometry, 4326) "
        "USING geom::geometry(Geometry, 4326)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE land_change_patches "
        "ALTER COLUMN geom TYPE geometry(Polygon, 4326) "
        "USING ST_GeometryN(geom, 1)::geometry(Polygon, 4326)"
    )

# -*- coding: utf-8 -*-
"""0007（v3.0）：结果表与标注表补充 GiST 空间索引（范围过滤走 Index Scan）。

Revision ID: 0007_gist_indexes_v3
Revises: 0006_patch_geom_generic
"""
from alembic import op

revision = "0007_gist_indexes_v3"
down_revision = "0006_patch_geom_generic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_land_change_patches_geom "
        "ON land_change_patches USING GIST (geom)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_suitability_grids_geom "
        "ON suitability_grids USING GIST (geom)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_map_features_geom "
        "ON map_features USING GIST (geom)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_land_change_patches_geom")
    op.execute("DROP INDEX IF EXISTS idx_suitability_grids_geom")
    op.execute("DROP INDEX IF EXISTS idx_map_features_geom")

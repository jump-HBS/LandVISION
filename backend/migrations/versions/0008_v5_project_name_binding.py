# -*- coding: utf-8 -*-
"""0008：V5.0 项目名绑定与冗余字段清理。

Revision ID: 0008_v5_project_name_binding
Revises: 0007_gist_indexes_v3
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_v5_project_name_binding"
down_revision = "0007_gist_indexes_v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 地块：项目 id 转项目名，并删除冗余字段。
    op.add_column("parcels", sa.Column("project_name", sa.String(100), nullable=True))
    op.execute(
        """
        UPDATE parcels p
        SET project_name = a.name
        FROM analysis_projects a
        WHERE p.project_id = a.id
        """
    )
    op.execute(
        """
        UPDATE parcels
        SET project_name = (SELECT name FROM analysis_projects ORDER BY id LIMIT 1)
        WHERE project_name IS NULL
        """
    )
    op.drop_index("idx_parcels_project", table_name="parcels")
    op.drop_column("parcels", "project_id")
    op.drop_column("parcels", "district")
    op.drop_column("parcels", "region_code")
    op.drop_column("parcels", "far_limit")
    op.drop_column("parcels", "height_limit")
    op.create_index("idx_parcels_project_name", "parcels", ["project_name"])

    # 兴趣点：项目 id 转项目名。
    op.add_column("pois", sa.Column("project_name", sa.String(100), nullable=True))
    op.execute(
        """
        UPDATE pois p
        SET project_name = a.name
        FROM analysis_projects a
        WHERE p.project_id = a.id
        """
    )
    op.execute(
        """
        UPDATE pois
        SET project_name = (SELECT name FROM analysis_projects ORDER BY id LIMIT 1)
        WHERE project_name IS NULL
        """
    )
    op.drop_index("idx_pois_project", table_name="pois")
    op.drop_column("pois", "project_id")
    op.create_index("idx_pois_project_name", "pois", ["project_name"])

    # 三区三线：项目 id 转项目名。
    op.add_column("planning_control",
                  sa.Column("project_name", sa.String(100), nullable=True))
    op.execute(
        """
        UPDATE planning_control p
        SET project_name = a.name
        FROM analysis_projects a
        WHERE p.project_id = a.id
        """
    )
    op.execute(
        """
        UPDATE planning_control
        SET project_name = (SELECT name FROM analysis_projects ORDER BY id LIMIT 1)
        WHERE project_name IS NULL
        """
    )
    op.drop_index("idx_planning_project", table_name="planning_control")
    op.drop_column("planning_control", "project_id")
    op.create_index("idx_planning_project_name", "planning_control", ["project_name"])

    # 地图标注：项目 id 转项目名。
    op.add_column("map_features",
                  sa.Column("project_name", sa.String(100), nullable=True))
    op.execute(
        """
        UPDATE map_features p
        SET project_name = a.name
        FROM analysis_projects a
        WHERE p.project_id = a.id
        """
    )
    op.execute(
        """
        UPDATE map_features
        SET project_name = (SELECT name FROM analysis_projects ORDER BY id LIMIT 1)
        WHERE project_name IS NULL
        """
    )
    op.drop_index("idx_mapfeat_project", table_name="map_features")
    op.drop_column("map_features", "project_id")
    op.create_index("idx_mapfeat_project_name", "map_features", ["project_name"])


def downgrade() -> None:
    # 地块：恢复项目 id 和冗余字段。
    op.add_column("parcels", sa.Column("project_id", sa.Integer(), nullable=True))
    op.add_column("parcels", sa.Column("district", sa.String(50), nullable=True))
    op.add_column("parcels", sa.Column("region_code", sa.String(20), nullable=True))
    op.add_column("parcels", sa.Column("far_limit", sa.Numeric(6, 2), nullable=True))
    op.add_column("parcels", sa.Column("height_limit", sa.Numeric(6, 2), nullable=True))
    op.execute(
        """
        UPDATE parcels p
        SET project_id = a.id
        FROM analysis_projects a
        WHERE p.project_name = a.name
        """
    )
    op.drop_index("idx_parcels_project_name", table_name="parcels")
    op.drop_column("parcels", "project_name")

    op.add_column("pois", sa.Column("project_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE pois p
        SET project_id = a.id
        FROM analysis_projects a
        WHERE p.project_name = a.name
        """
    )
    op.drop_index("idx_pois_project_name", table_name="pois")
    op.drop_column("pois", "project_name")

    op.add_column("planning_control",
                  sa.Column("project_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE planning_control p
        SET project_id = a.id
        FROM analysis_projects a
        WHERE p.project_name = a.name
        """
    )
    op.drop_index("idx_planning_project_name", table_name="planning_control")
    op.drop_column("planning_control", "project_name")

    op.add_column("map_features",
                  sa.Column("project_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE map_features p
        SET project_id = a.id
        FROM analysis_projects a
        WHERE p.project_name = a.name
        """
    )
    op.drop_index("idx_mapfeat_project_name", table_name="map_features")
    op.drop_column("map_features", "project_name")

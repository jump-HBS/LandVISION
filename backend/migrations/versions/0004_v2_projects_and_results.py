# -*- coding: utf-8 -*-
"""0004：v2.0 数据基础升级 —— 分析项目 + 结果持久化 + 期次/锁定/项目归属字段。

Revision ID: 0004_v2_projects_and_results
Revises: 0003_drop_change_records
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0004_v2_projects_and_results"
down_revision = "0003_drop_change_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------- 分析项目 ----------
    op.create_table(
        "analysis_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("base_year", sa.Integer(), nullable=False),
        sa.Column("current_year", sa.Integer(), nullable=False),
        sa.Column("scope_geojson", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ---------- 地块：期次必填（默认基期）+ 项目归属 + 锁定 ----------
    op.execute("UPDATE parcels SET period = 'base' WHERE period IS NULL")
    op.alter_column("parcels", "period", existing_type=sa.String(10), nullable=False,
                    server_default="base")
    op.add_column("parcels", sa.Column("project_id", sa.Integer(),
                                       sa.ForeignKey("analysis_projects.id", ondelete="SET NULL"),
                                       nullable=True))
    op.add_column("parcels", sa.Column("locked", sa.Boolean(), nullable=False,
                                       server_default=sa.false()))
    op.create_index("idx_parcels_project", "parcels", ["project_id"])

    # ---------- POI：项目归属 + 期次 + 锁定 ----------
    op.add_column("pois", sa.Column("project_id", sa.Integer(),
                                    sa.ForeignKey("analysis_projects.id", ondelete="SET NULL"),
                                    nullable=True))
    op.add_column("pois", sa.Column("period", sa.String(10), nullable=True))
    op.add_column("pois", sa.Column("locked", sa.Boolean(), nullable=False,
                                    server_default=sa.false()))
    op.create_index("idx_pois_project", "pois", ["project_id"])

    # ---------- 规划控制要素：项目归属 + 期次 + 锁定 ----------
    op.add_column("planning_control", sa.Column("project_id", sa.Integer(),
                                                sa.ForeignKey("analysis_projects.id", ondelete="SET NULL"),
                                                nullable=True))
    op.add_column("planning_control", sa.Column("period", sa.String(10), nullable=True))
    op.add_column("planning_control", sa.Column("locked", sa.Boolean(), nullable=False,
                                                server_default=sa.false()))
    op.create_index("idx_planning_project", "planning_control", ["project_id"])

    # ---------- 转移矩阵变化图斑（结果持久化） ----------
    op.create_table(
        "land_change_patches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("analysis_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_land_use", sa.String(50)),
        sa.Column("to_land_use", sa.String(50)),
        sa.Column("area_sqm", sa.Numeric(14, 2)),
        sa.Column("change_type", sa.String(50), nullable=False),  # 新增/消失/转换
        sa.Column("is_conflict", sa.Boolean(), nullable=True),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_patches_project", "land_change_patches", ["project_id"])

    # ---------- 适宜性评价格网（结果持久化） ----------
    op.create_table(
        "suitability_grids",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("analysis_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(6, 2)),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("factors_json", sa.JSON(), nullable=True),
        sa.Column("geom", Geometry("POLYGON", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_grids_project", "suitability_grids", ["project_id"])

    # ---------- 三区三线体检结果（结果持久化） ----------
    op.create_table(
        "planning_check_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("analysis_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parcel_id", sa.Integer(),
                  sa.ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("zone_id", sa.Integer(),
                  sa.ForeignKey("planning_control.id", ondelete="SET NULL"), nullable=True),
        sa.Column("overlap_area_sqm", sa.Numeric(14, 2)),
        sa.Column("conclusion", sa.String(20), nullable=False),  # 冲突/警告/提示/通过
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_checkres_project", "planning_check_results", ["project_id"])
    op.create_index("idx_checkres_parcel", "planning_check_results", ["parcel_id"])

    # ---------- 可达性分析结果（结果持久化） ----------
    op.create_table(
        "accessibility_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("analysis_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("facility_types", sa.JSON(), nullable=True),
        sa.Column("radius_m", sa.Numeric(10, 2)),
        sa.Column("parcel_total", sa.Integer()),
        sa.Column("covered_count", sa.Integer()),
        sa.Column("coverage_rate", sa.Numeric(8, 6)),
        sa.Column("gap_parcel_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_accessres_project", "accessibility_results", ["project_id"])

    # ---------- 地图编辑标注（地图绘制持久化） ----------
    op.create_table(
        "map_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("analysis_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("feature_type", sa.String(20), nullable=False),  # point/line/polygon
        sa.Column("category", sa.String(50)),
        sa.Column("properties_json", sa.JSON(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("geom", Geometry("GEOMETRY", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_mapfeat_project", "map_features", ["project_id"])


def downgrade() -> None:
    op.drop_table("map_features")
    op.drop_table("accessibility_results")
    op.drop_table("planning_check_results")
    op.drop_table("suitability_grids")
    op.drop_table("land_change_patches")
    op.drop_index("idx_planning_project", table_name="planning_control")
    op.drop_column("planning_control", "locked")
    op.drop_column("planning_control", "period")
    op.drop_column("planning_control", "project_id")
    op.drop_index("idx_pois_project", table_name="pois")
    op.drop_column("pois", "locked")
    op.drop_column("pois", "period")
    op.drop_column("pois", "project_id")
    op.drop_index("idx_parcels_project", table_name="parcels")
    op.drop_column("parcels", "locked")
    op.drop_column("parcels", "project_id")
    op.alter_column("parcels", "period", existing_type=sa.String(10), nullable=True,
                    server_default=None)
    op.drop_table("analysis_projects")

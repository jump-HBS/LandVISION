# -*- coding: utf-8 -*-
"""0005：三区三线管控区类型术语规范化（中文 → 标准英文代码）。

Revision ID: 0005_standardize_zone_types
Revises: 0004_v2_projects_and_results
"""
from alembic import op

revision = "0005_standardize_zone_types"
down_revision = "0004_v2_projects_and_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE planning_control SET zone_type = CASE "
        "WHEN zone_type = '生态保护红线' THEN 'ecological_red_line' "
        "WHEN zone_type = '永久基本农田' THEN 'permanent_basic_farmland' "
        "WHEN zone_type = '城镇开发边界' THEN 'urban_growth_boundary' "
        "ELSE zone_type END"
    )
    # 非标准类型（历史自定义"其他/历史文化保护区"）直接移除：三线由用户自行导入
    op.execute(
        "DELETE FROM planning_control WHERE zone_type NOT IN "
        "('permanent_basic_farmland', 'ecological_red_line', 'urban_growth_boundary')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE planning_control SET zone_type = CASE "
        "WHEN zone_type = 'ecological_red_line' THEN '生态保护红线' "
        "WHEN zone_type = 'permanent_basic_farmland' THEN '永久基本农田' "
        "WHEN zone_type = 'urban_growth_boundary' THEN '城镇开发边界' "
        "ELSE zone_type END"
    )

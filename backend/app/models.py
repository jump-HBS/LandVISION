# -*- coding: utf-8 -*-
"""
ORM 模型：业务表 + v2.0 项目/结果持久化表（与 Alembic 迁移 0001~0005 一一对应）。

关键点：空间字段用 GeoAlchemy2 的 Geometry 类型声明：
    geom = Column(Geometry("POLYGON", srid=4326))
数据库里实际存储类型为 geometry(Polygon, 4326)，
SQLAlchemy 读写时自动完成 Python 对象 ↔ 数据库几何的转换。
"""
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        Numeric, String, Text, func)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AnalysisProject(Base):
    """分析项目：所有分析活动的业务上下文（范围 + 期次年份）。"""

    __tablename__ = "analysis_projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    base_year = Column(Integer, nullable=False)                 # 基期年份
    current_year = Column(Integer, nullable=False)              # 末期年份
    scope_geojson = Column(JSON, nullable=True)                 # 分析范围（None=全量）
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Parcel(Base):
    """地块表。"""

    __tablename__ = "parcels"

    id = Column(Integer, primary_key=True)
    parcel_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    land_use = Column(String(50), nullable=False)   # GB/T 21010-2017 一级类（12 大类）
    district = Column(String(50))                   # 行政区名称（如 武汉市洪山区）
    region_code = Column(String(20))                # 行政区划代码（如 420111）
    period = Column(String(10), nullable=False, default="base", server_default="base")  # base/current
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="SET NULL"))
    locked = Column(Boolean, nullable=False, default=False, server_default="false")
    area_sqm = Column(Numeric(14, 2))
    far_limit = Column(Numeric(6, 2))
    height_limit = Column(Numeric(6, 2))
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Poi(Base):
    """兴趣点表。"""

    __tablename__ = "pois"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    poi_type = Column(String(50), nullable=False)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="SET NULL"))
    period = Column(String(10))
    locked = Column(Boolean, nullable=False, default=False, server_default="false")
    geom = Column(Geometry("POINT", srid=4326), nullable=False)


class PlanningZone(Base):
    """规划控制区表（三区三线，标准英文类型代码）。"""

    __tablename__ = "planning_control"

    id = Column(Integer, primary_key=True)
    zone_name = Column(String(100), nullable=False)
    # permanent_basic_farmland / ecological_red_line / urban_growth_boundary
    zone_type = Column(String(50), nullable=False)
    zone_level = Column(String(20))
    control_desc = Column(Text)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="SET NULL"))
    period = Column(String(10))
    locked = Column(Boolean, nullable=False, default=False, server_default="false")
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False)


class Region(Base):
    """行政区划表：省 / 市 / 县 三级（省级内置，市县级通过 SHP 导入）。"""

    __tablename__ = "regions"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)   # 行政区划代码（GB/T 2260）
    name = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False)               # province / city / county
    parent_code = Column(String(20))                         # 上级代码（省级为 100000）
    geom = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)


class LandChangePatch(Base):
    """转移矩阵变化图斑（结果持久化，模块间复用）。"""

    __tablename__ = "land_change_patches"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="CASCADE"),
                        nullable=False)
    from_land_use = Column(String(50))
    to_land_use = Column(String(50))
    area_sqm = Column(Numeric(14, 2))
    change_type = Column(String(50), nullable=False)   # 新增/消失/转换
    is_conflict = Column(Boolean)                      # 体检结论（冲突），联动填充
    geom = Column(Geometry("GEOMETRY", srid=4326), nullable=False)  # 可能为 MultiPolygon
    created_at = Column(DateTime, server_default=func.now())


class SuitabilityGrid(Base):
    """适宜性评价格网（结果持久化）。"""

    __tablename__ = "suitability_grids"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="CASCADE"),
                        nullable=False)
    score = Column(Numeric(6, 2))
    level = Column(String(20), nullable=False)   # 高度适宜/中等适宜/勉强适宜/不适宜
    factors_json = Column(JSON)
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class PlanningCheckResult(Base):
    """三区三线体检结果（地块 × 管控区，结果持久化）。"""

    __tablename__ = "planning_check_results"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="CASCADE"),
                        nullable=False)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="SET NULL"))
    zone_id = Column(Integer, ForeignKey("planning_control.id", ondelete="SET NULL"))
    overlap_area_sqm = Column(Numeric(14, 2))
    conclusion = Column(String(20), nullable=False)   # 冲突/警告/提示/通过
    created_at = Column(DateTime, server_default=func.now())


class AccessibilityResult(Base):
    """可达性分析结果（结果持久化，保留盲区地块 ID 列表）。"""

    __tablename__ = "accessibility_results"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="CASCADE"),
                        nullable=False)
    facility_types = Column(JSON)
    radius_m = Column(Numeric(10, 2))
    parcel_total = Column(Integer)
    covered_count = Column(Integer)
    coverage_rate = Column(Numeric(8, 6))
    gap_parcel_ids = Column(JSON)   # 盲区地块 id 列表
    created_at = Column(DateTime, server_default=func.now())


class MapFeature(Base):
    """地图编辑标注（地图上绘制的点/线/面持久化，支持锁定与批量删除）。"""

    __tablename__ = "map_features"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("analysis_projects.id", ondelete="SET NULL"))
    name = Column(String(100), nullable=False)
    feature_type = Column(String(20), nullable=False)   # point / line / polygon
    category = Column(String(50))
    properties_json = Column(JSON)
    locked = Column(Boolean, nullable=False, default=False, server_default="false")
    geom = Column(Geometry("GEOMETRY", srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

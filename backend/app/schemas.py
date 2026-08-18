# -*- coding: utf-8 -*-
"""
Pydantic 模型（请求/响应数据格式定义）。

设计约定：
  * 几何一律使用 GeoJSON 字典（{"type": ..., "coordinates": ...}）在 API 层传输；
  * 用地性质遵循 GB/T 21010-2017 一级类（12 大类），输入做枚举校验；
  * 三区三线类型使用标准英文代码（见 ZONE_TYPE_LABELS），界面展示中文标签；
  * 创建/更新用 Base/Create 模型做输入校验，响应由服务层组装为 dict 直接返回。
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# GB/T 21010-2017 一级类（12 大类）
LAND_USE_TYPES: List[str] = [
    "耕地", "园地", "林地", "草地", "商服用地", "工矿仓储用地", "住宅用地",
    "公共管理与公共服务用地", "特殊用地", "交通运输用地", "水域及水利设施用地", "其他土地",
]

# ---------- 三区三线标准类型（英文代码，界面显示中文标签） ----------
ZONE_TYPE_LABELS: Dict[str, str] = {
    "permanent_basic_farmland": "永久基本农田",
    "ecological_red_line": "生态保护红线",
    "urban_growth_boundary": "城镇开发边界",
}
ZONE_TYPES: List[str] = list(ZONE_TYPE_LABELS)
REVIEW_ZONE_TYPES: List[str] = ZONE_TYPES  # 兼容别名

# 结论等级（体检）：冲突 > 警告 > 提示 > 通过
VERDICT_LEVELS: List[str] = ["冲突", "警告", "提示", "通过"]


# ---------- 地块 ----------
class ParcelBase(BaseModel):
    parcel_code: str = Field(..., min_length=1, max_length=50, description="地块编号")
    name: str = Field(..., min_length=1, max_length=100, description="地块名称")
    land_use: str = Field(..., description="用地性质（GB/T 21010-2017 一级类）")
    district: Optional[str] = Field(None, max_length=50, description="行政区名称（如 武汉市洪山区）")
    region_code: Optional[str] = Field(None, max_length=20, description="行政区划代码（如 420111）")
    area_sqm: Optional[float] = Field(None, ge=0, description="面积（平方米）")
    far_limit: Optional[float] = Field(None, ge=0, description="容积率上限")
    height_limit: Optional[float] = Field(None, ge=0, description="建筑限高（米）")

    @field_validator("land_use")
    @classmethod
    def _validate_land_use(cls, v: str) -> str:
        if v not in LAND_USE_TYPES:
            raise ValueError(f"用地性质必须为 GB/T 21010-2017 一级类之一：{'/'.join(LAND_USE_TYPES)}")
        return v


class ParcelCreate(ParcelBase):
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Polygon 几何")
    period: str = Field("base", description="期次：base（基期）/ current（末期）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id")
    locked: bool = Field(False, description="锁定（锁定后不可删除）")

    @field_validator("period")
    @classmethod
    def _validate_period(cls, v: str) -> str:
        if v not in ("base", "current"):
            raise ValueError("期次必须为 base（基期）或 current（末期）")
        return v


class ParcelUpdate(BaseModel):
    name: Optional[str] = None
    land_use: Optional[str] = None
    district: Optional[str] = None
    region_code: Optional[str] = None
    period: Optional[str] = None
    project_id: Optional[int] = None
    locked: Optional[bool] = None
    area_sqm: Optional[float] = Field(None, ge=0)
    far_limit: Optional[float] = Field(None, ge=0)
    height_limit: Optional[float] = Field(None, ge=0)
    geometry: Optional[Dict[str, Any]] = None

    @field_validator("land_use")
    @classmethod
    def _validate_land_use(cls, v):
        if v is not None and v not in LAND_USE_TYPES:
            raise ValueError(f"用地性质必须为 GB/T 21010-2017 一级类之一：{'/'.join(LAND_USE_TYPES)}")
        return v

    @field_validator("period")
    @classmethod
    def _validate_period(cls, v):
        if v is not None and v not in ("base", "current"):
            raise ValueError("期次必须为 base（基期）或 current（末期）")
        return v


# ---------- 兴趣点 ----------
class PoiBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    poi_type: str = Field(..., description="交通/商业/教育/医疗/休闲")


class PoiCreate(PoiBase):
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Point 几何")
    project_id: Optional[int] = Field(None, description="所属分析项目 id")
    period: Optional[str] = Field(None, description="期次（可选）")
    locked: bool = Field(False)


class PoiUpdate(BaseModel):
    name: Optional[str] = None
    poi_type: Optional[str] = None
    project_id: Optional[int] = None
    locked: Optional[bool] = None
    geometry: Optional[Dict[str, Any]] = None


# ---------- 规划审查：任意几何检查专用 ----------
class GeometryCheck(BaseModel):
    geometry: Dict[str, Any] = Field(..., description="任意 GeoJSON 几何（Point/LineString/Polygon）")
    land_use: str = Field("其他土地", description="用地性质（用于规则矩阵判定，缺省=其他土地）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id（用于规则范围校验）")

    @field_validator("land_use")
    @classmethod
    def _validate_land_use(cls, v: str) -> str:
        if v not in LAND_USE_TYPES:
            raise ValueError(f"用地性质必须为 GB/T 21010-2017 一级类之一：{'/'.join(LAND_USE_TYPES)}")
        return v


# ---------- v3.0：按几何范围批量删除 ----------
class GeometryDelete(BaseModel):
    geometry: Dict[str, Any] = Field(..., description="删除范围 GeoJSON（Polygon，地图框选）")
    mode: str = Field("intersects", description="intersects=与范围相交 / within=完全位于范围内")


# ---------- 空间分析（转移矩阵 / 适宜性 / 可达性） ----------
class ScopeBody(BaseModel):
    """通用范围请求体。"""

    scope: Optional[Dict[str, Any]] = Field(None, description="分析范围 GeoJSON（可选）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id（用于持久化与范围校验）")


class SuitabilityRequest(BaseModel):
    target: str = Field("建设用地适宜性", description="评价目标")
    weights: Dict[str, float] = Field(default_factory=dict, description="因子权重（缺省用内置默认）")
    scope: Optional[Dict[str, Any]] = Field(None, description="评价范围 GeoJSON（缺省继承项目范围）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id（用于持久化）")


class AccessibilityRequest(BaseModel):
    facility_types: List[str] = Field(default_factory=list, description="设施类型（空=全部）")
    radius_m: float = Field(800, ge=100, le=10000, description="服务半径（米）")
    scope: Optional[Dict[str, Any]] = Field(None, description="分析范围 GeoJSON（可选）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id（用于持久化）")


# ---------- 规划审查：审查地块（三区三线）与批量审查 ----------
class ZoneCreate(BaseModel):
    """新增三区三线控制线（zone_type 为标准三线英文代码）。"""

    zone_name: str = Field(..., min_length=1, max_length=100, description="控制线名称")
    zone_type: str = Field(..., description="permanent_basic_farmland / ecological_red_line / urban_growth_boundary")
    zone_level: Optional[str] = Field(None, max_length=20, description="级别（可选）")
    control_desc: Optional[str] = Field(None, max_length=500, description="管控说明（可选）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id")
    period: Optional[str] = Field(None, description="期次（可选）")
    locked: bool = Field(False)
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Polygon 几何")

    @field_validator("zone_type")
    @classmethod
    def _validate_zone_type(cls, v: str) -> str:
        if v not in ZONE_TYPE_LABELS:
            raise ValueError(f"管控区类型必须为：{'/'.join(ZONE_TYPES)}")
        return v


class ReviewRequest(BaseModel):
    """批量审查：在审查范围内，计算所选地块占用各类型控制线的面积。"""

    scope: Optional[Dict[str, Any]] = Field(None, description="审查范围 GeoJSON（可选，不限范围）")
    zone_ids: Optional[List[int]] = Field(None, description="参与的控制线 id（None=范围内全部）")
    parcel_ids: Optional[List[int]] = Field(None, description="被审查地块 id（None=范围内全部）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id（用于持久化）")


class PatchReviewRequest(BaseModel):
    """对转移矩阵变化图斑做三区三线合规检查。"""

    project_id: int = Field(..., description="分析项目 id（图斑已按项目持久化）")
    patch_ids: Optional[List[int]] = Field(None, description="图斑 id 列表（None=该项目全部图斑）")


# ---------- 分析项目 ----------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="项目名称（唯一）")
    base_year: int = Field(..., ge=1990, le=2100, description="基期年份")
    current_year: int = Field(..., ge=1990, le=2100, description="末期年份")
    scope: Optional[Dict[str, Any]] = Field(None, description="分析范围 GeoJSON（None=全量）")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_year: Optional[int] = Field(None, ge=1990, le=2100)
    current_year: Optional[int] = Field(None, ge=1990, le=2100)
    scope: Optional[Dict[str, Any]] = Field(None, description="新分析范围 GeoJSON")
    confirm_scope_change: bool = Field(False, description="范围变更确认（已有分析结果可能失效）")


# ---------- 数据驾驶舱 / 报告（共用统筹数据源） ----------
class DashboardSummaryRequest(BaseModel):
    """驾驶舱统筹汇总请求：按分析项目与范围聚合各模块统计数据（优先读取持久化结果）。"""

    project_id: Optional[int] = Field(None, description="分析项目 id")
    scope: Optional[Dict[str, Any]] = Field(None, description="分析范围 GeoJSON（可选，None=项目范围/全量）")
    scope_label: Optional[str] = Field(None, max_length=100, description="范围名称")


class ReportRequest(BaseModel):
    project_name: str = Field("云帆新城国土空间数据管理报告", max_length=100)
    period: str = Field("2026 年第三季度", max_length=50)
    author: str = Field("LandVISION 系统", max_length=50)
    project_id: Optional[int] = Field(None, description="分析项目 id（继承自数据驾驶舱）")
    scope: Optional[Dict[str, Any]] = Field(None, description="分析范围 GeoJSON（继承自数据驾驶舱，None=全量）")
    scope_label: Optional[str] = Field(None, max_length=100, description="分析范围名称")


# ---------- 规则矩阵 ----------
class RuleUpdate(BaseModel):
    """体检规则矩阵更新：rules 为 [(land_use, zone_type) → conclusion] 列表。"""

    rules: List[Dict[str, str]] = Field(..., description="规则列表 [{land_use, zone_type, conclusion}]")


# ---------- 批量操作 / 锁定 / 地图标注 ----------
class BatchIdsBody(BaseModel):
    ids: List[int] = Field(..., min_length=1, description="待操作对象 id 列表")


class LockBody(BaseModel):
    locked: bool = Field(..., description="true=锁定，false=解除锁定")


class MapFeatureCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="标注名称")
    feature_type: str = Field(..., description="point / line / polygon")
    category: Optional[str] = Field(None, max_length=50, description="分类（可选）")
    project_id: Optional[int] = Field(None, description="所属分析项目 id")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加属性")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON 几何（Point/LineString/Polygon）")

    @field_validator("feature_type")
    @classmethod
    def _validate_feature_type(cls, v: str) -> str:
        if v not in ("point", "line", "polygon"):
            raise ValueError("feature_type 必须为 point / line / polygon")
        return v


# ---------- 行政区 ----------
class RegionOut(BaseModel):
    code: str
    name: str
    level: str
    parent_code: Optional[str] = None


# ---------- 分页 ----------
class PageParams(BaseModel):
    """分页查询参数（各列表接口共用）。"""

    page: int = Field(1, ge=1, description="页码（从 1 开始）")
    page_size: int = Field(20, ge=1, le=100, description="每页条数（1~100）")


def paginated(items: list, page: int, page_size: int, total: int) -> dict:
    """分页响应统一结构：{items, total, page, page_size, pages}。"""
    pages = (total + page_size - 1) // page_size if page_size else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# ---------- ORM 输出模型 ----------
class ParcelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_code: str
    name: str
    land_use: str
    district: Optional[str] = None
    region_code: Optional[str] = None
    period: Optional[str] = None
    project_id: Optional[int] = None
    locked: Optional[bool] = None
    area_sqm: Optional[float] = None
    far_limit: Optional[float] = None
    height_limit: Optional[float] = None


class PoiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    poi_type: str
    project_id: Optional[int] = None

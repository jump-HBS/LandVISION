# -*- coding: utf-8 -*-
"""路由组：空间分析 analysis —— 转移矩阵 / 适宜性评价 / 可达性分析（模块一~三）+ 结果查询与联动。"""
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile)

from ..config import settings
from ..database import get_db
from ..schemas import AccessibilityRequest, ScopeBody, SuitabilityRequest
from ..services import analysis, shp_import

router = APIRouter(prefix="/analysis", tags=["空间分析"])


# ===========================================================================
# 模块一：用地变化转移矩阵
# ===========================================================================

@router.post("/transition/import-shp", summary="导入期次地块 SHP（base 基期 / current 末期，关联项目）")
async def transition_import(
    file: UploadFile = File(..., description="SHP 压缩包（WGS84，面要素）"),
    period: str = Form(..., description="期次：base（基期）/ current（末期）"),
    name_field: Optional[str] = Form(None),
    land_use_field: Optional[str] = Form(None),
    region_code: Optional[str] = Form(None),
    project_id: Optional[int] = Form(None, description="所属分析项目 id"),
    db=Depends(get_db),
):
    if period not in ("base", "current"):
        raise HTTPException(status_code=422, detail="period 必须为 base 或 current")
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="请上传 zip 压缩包")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"压缩包超过 {settings.max_upload_mb}MB 上限")
    try:
        return analysis.import_period_parcels(
            db, content, period=period,
            name_field=name_field, land_use_field=land_use_field,
            region_code=region_code, project_id=project_id,
        )
    except (shp_import.ShpImportError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/transition/generate-demo-base", summary="一键生成演示基期（模拟三处变化）")
def generate_demo_base(body: ScopeBody, db=Depends(get_db)):
    return analysis.generate_demo_base(db, project_id=body.project_id)


@router.post("/transition/matrix", summary="计算用地转移矩阵（继承项目范围，结果持久化）")
def transition_matrix(body: ScopeBody, db=Depends(get_db)):
    try:
        return analysis.transition_matrix(db, scope=body.scope, project_id=body.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/transition/patches", summary="查询变化图斑（持久化数据，按项目）")
def transition_patches(project_id: Optional[int] = None, db=Depends(get_db)):
    return analysis.list_patches(db, project_id=project_id)


# ===========================================================================
# 模块二：土地适宜性评价
# ===========================================================================

@router.get("/suitability/targets", summary="评价目标与默认因子权重")
def suitability_targets():
    return analysis.SUITABILITY_TARGETS


@router.post("/suitability/evaluate", summary="多因子加权叠加评价（格网法 + 刚性约束 + 持久化）")
def suitability_evaluate(body: SuitabilityRequest, db=Depends(get_db)):
    targets = analysis.SUITABILITY_TARGETS
    if body.target not in targets:
        raise HTTPException(status_code=422, detail=f"评价目标必须为：{'/'.join(targets)}")
    # 权重补默认
    defaults = {f["key"]: f["default"] for f in targets[body.target]["factors"]}
    weights = {**defaults, **{k: v for k, v in body.weights.items() if k in defaults}}
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}
    try:
        return analysis.suitability_evaluate(db, body.target, weights, body.scope,
                                             project_id=body.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/suitability/grids", summary="查询适宜性评价格网（持久化数据，按项目）")
def suitability_grids(project_id: Optional[int] = None, db=Depends(get_db)):
    return analysis.list_grids(db, project_id=project_id)


# ===========================================================================
# 模块三：服务设施可达性分析
# ===========================================================================

@router.post("/accessibility/analyze", summary="设施可达性分析（生活圈覆盖与盲区，结果持久化）")
def accessibility_analyze(body: AccessibilityRequest, db=Depends(get_db)):
    try:
        return analysis.accessibility_analyze(
            db, facility_types=body.facility_types, radius_m=body.radius_m,
            scope=body.scope, project_id=body.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/accessibility/results", summary="查询可达性分析结果（持久化数据，按项目）")
def accessibility_results(project_id: Optional[int] = None, db=Depends(get_db)):
    return analysis.list_accessibility(db, project_id=project_id)


# ===========================================================================
# 模块联动：可达性盲区 ∩ 适宜性 → 建议新增设施选址
# ===========================================================================

@router.get("/facility-sites", summary="推荐设施选址（盲区 ∩ 高度/中等适宜格网，模块三↔二联动）")
def facility_sites(project_id: int, db=Depends(get_db)):
    return analysis.facility_sites(db, project_id=project_id)


# ===========================================================================
# 通用：SHP 范围解析（各分析页"导入 SHP 范围"共用，不落库）
# ===========================================================================

@router.post("/parse-scope", summary="解析 SHP 压缩包为分析范围几何（不落库，取全部要素并集）")
async def parse_scope(
    file: UploadFile = File(..., description="SHP 压缩包（WGS84，面要素）"),
    db=Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="请上传 zip 压缩包（含 .shp/.shx/.dbf/.prj）")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422,
                            detail=f"压缩包超过 {settings.max_upload_mb}MB 上限")
    try:
        from shapely.ops import unary_union
        from shapely.geometry import shape, mapping
        parsed = shp_import.parse_shp_zip(content)
        geoms = [
            shape(f["geometry"]) for f in parsed["features"]
            if f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        ]
        if not geoms:
            raise HTTPException(status_code=422, detail="文件中没有可用的面要素")
        merged = unary_union(geoms)
        return {
            "feature_count": len(geoms),
            "scope": mapping(merged),
            "bbox": list(merged.bounds),
        }
    except (shp_import.ShpImportError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

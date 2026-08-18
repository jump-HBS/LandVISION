# -*- coding: utf-8 -*-
"""路由组：三区三线体检 planning —— 控制线管理 / 规则矩阵 / 合规检查 / 批量体检 / 图斑体检 / 台账。"""
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile)
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..database import get_db
from ..schemas import (ZONE_TYPE_LABELS, BatchIdsBody, GeometryCheck, LockBody,
                       PatchReviewRequest, ReviewRequest, RuleUpdate, ZoneCreate)
from ..services import planning_check, planning_rules
from ..services.spatial import is_demo

router = APIRouter(prefix="/planning", tags=["三区三线体检"])


# ---------- 三区三线控制线 ----------
@router.get("/zones", summary="控制线列表（三区三线）")
def list_zones(db=Depends(get_db)):
    return planning_check.list_zones(db)


@router.get("/zones/geojson", summary="控制线 GeoJSON")
def zones_geojson(db=Depends(get_db)):
    return planning_check.zones_geojson(db)


@router.post("/zones", summary="新增控制线（标准三线，支持图上绘制）", status_code=201)
def create_zone(body: ZoneCreate, db=Depends(get_db)):
    try:
        return planning_check.create_zone(body.model_dump(), db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/zones/{zone_id}", summary="删除控制线（锁定后不可删除）", status_code=204)
def delete_zone(zone_id: int, db=Depends(get_db)):
    try:
        ok = planning_check.delete_zone(zone_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail="控制线不存在")


@router.post("/zones/batch-delete", summary="批量删除控制线（跳过锁定项）")
def batch_delete_zones(body: BatchIdsBody, db=Depends(get_db)):
    deleted, locked, missing = [], [], []
    for zid in body.ids:
        zone = next((z for z in planning_check.list_zones(db) if z["id"] == zid), None)
        if not zone:
            missing.append(zid)
            continue
        if zone.get("locked"):
            locked.append({"id": zid, "name": zone["zone_name"]})
            continue
        planning_check.delete_zone(zid, db)
        deleted.append(zid)
    return {"deleted": deleted, "locked": locked, "missing": missing}


@router.post("/zones/{zone_id}/lock", summary="锁定 / 解锁控制线")
def lock_zone(zone_id: int, body: LockBody, db=Depends(get_db)):
    if is_demo():
        from .. import demo_data
        z = next((x for x in demo_data.PLANNING_ZONES if x["id"] == zone_id), None)
        if not z:
            raise HTTPException(status_code=404, detail="控制线不存在")
        z["locked"] = body.locked
        return {"id": zone_id, "locked": body.locked}
    from ..models import PlanningZone
    row = db.query(PlanningZone).filter(PlanningZone.id == zone_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="控制线不存在")
    row.locked = body.locked
    db.commit()
    return {"id": zone_id, "locked": body.locked}


@router.post("/zones/import-shp", summary="SHP 批量导入三区三线控制线（边界由用户导入，类型统一指定）")
async def import_zones_shp(
    file: UploadFile = File(..., description="SHP 压缩包（WGS84）"),
    zone_type: Optional[str] = Form(None, description="统一类型：permanent_basic_farmland / ecological_red_line / urban_growth_boundary"),
    name_field: Optional[str] = Form(None, description="要素名称字段（可自动识别）"),
    type_field: Optional[str] = Form(None, description="类型字段（未指定 zone_type 时容错映射）"),
    project_id: Optional[int] = Form(None, description="所属分析项目 id"),
    period: Optional[str] = Form(None, description="期次（可选）"),
    db=Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="请上传 zip 压缩包（含 .shp/.shx/.dbf/.prj）")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422,
                            detail=f"压缩包超过 {settings.max_upload_mb}MB 上限")
    try:
        from ..services import shp_import
        return planning_check.import_zones_from_zip(
            content, db, name_field=name_field, type_field=type_field,
            zone_type=zone_type, project_id=project_id, period=period,
        )
    except (shp_import.ShpImportError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ---------- 体检规则矩阵 ----------
@router.get("/rules", summary="体检规则矩阵（12 用地大类 × 三区三线）")
def get_rules():
    return {
        "zone_types": [{"code": z, "label": l} for z, l in ZONE_TYPE_LABELS.items()],
        "rows": planning_rules.rules_table(),
    }


@router.put("/rules", summary="更新体检规则矩阵（配置化）")
def update_rules(body: RuleUpdate):
    try:
        matrix = {}
        for item in body.rules:
            matrix.setdefault(item["land_use"], {})[item["zone_type"]] = item["conclusion"]
        planning_rules.save_matrix(matrix)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"updated": True, "rows": planning_rules.rules_table()}


# ---------- 合规检查 ----------
@router.get("/check/{parcel_id}", summary="单地块三区三线体检（含判定依据）")
def check_parcel(parcel_id: int, db=Depends(get_db)):
    data = planning_check.check_parcel(parcel_id, db)
    if not data:
        raise HTTPException(status_code=404, detail="地块不存在")
    return data


@router.post("/check", summary="对任意 GeoJSON 几何做体检（不落库）")
def check_geometry(body: GeometryCheck, db=Depends(get_db)):
    return planning_check.check_geometry(body.geometry, body.land_use, db)


# ---------- 批量体检 + 结果持久化 + 台账导出 ----------
@router.post("/review", summary="批量体检：范围内地块占用各控制线面积（结果按项目持久化）")
def review(body: ReviewRequest, db=Depends(get_db)):
    return planning_check.review_occupancy(
        db, scope=body.scope, zone_ids=body.zone_ids, parcel_ids=body.parcel_ids,
        project_id=body.project_id,
    )


@router.post("/review-patches", summary="对转移矩阵变化图斑做合规检查（模块一→四联动）")
def review_patches(body: PatchReviewRequest, db=Depends(get_db)):
    return planning_check.review_patches(db, project_id=body.project_id,
                                         patch_ids=body.patch_ids)


@router.get("/results", summary="查询体检结果（持久化数据，按项目/地块过滤）")
def list_results(project_id: Optional[int] = None, parcel_id: Optional[int] = None,
                 db=Depends(get_db)):
    return planning_check.list_results(db, project_id=project_id, parcel_id=parcel_id)


@router.post("/review/export", summary="导出问题台账 CSV（三区三线体检结果）")
def review_export(body: ReviewRequest, db=Depends(get_db)):
    result = planning_check.review_occupancy(
        db, scope=body.scope, zone_ids=body.zone_ids, parcel_ids=body.parcel_ids,
        project_id=body.project_id,
    )
    csv_text = planning_check.review_to_csv(result)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="planning_review_ledger.csv"'},
    )

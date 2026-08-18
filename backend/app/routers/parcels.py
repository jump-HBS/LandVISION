# -*- coding: utf-8 -*-
"""路由组：地块 parcels —— 分页列表 / 视野查询 / GeoJSON / CRUD / SHP 批量导入 / 批量删除 / 锁定 / 期次。"""
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     UploadFile)

from ..config import settings
from ..database import get_db
from ..schemas import BatchIdsBody, LockBody, ParcelCreate, ParcelUpdate
from ..services import shp_import, spatial

router = APIRouter(prefix="/parcels", tags=["地块管理"])


@router.get("", summary="地块分页列表（表格数据，可按期次过滤）")
def list_parcels(
    bbox: Optional[str] = Query(None, description="视野范围 minx,miny,maxx,maxy"),
    land_use: Optional[str] = Query(None, description="按用地性质过滤（12 大类）"),
    district: Optional[str] = Query(None, description="按行政区名称过滤"),
    region_code: Optional[str] = Query(None, description="按行政区划代码过滤（如 420111）"),
    period: Optional[str] = Query(None, description="期次过滤：base（基期）/ current（末期）"),
    q: Optional[str] = Query(None, description="按名称/编号模糊搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    try:
        return spatial.list_parcels(
            db, bbox=bbox, land_use=land_use, q=q, district=district,
            region_code=region_code, period=period, page=page, page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/geojson", summary="地块 GeoJSON（地图渲染，可按期次过滤）")
def parcels_geojson(
    bbox: Optional[str] = Query(None, description="视野范围 minx,miny,maxx,maxy"),
    period: Optional[str] = Query(None, description="期次过滤：base（基期）/ current（末期）"),
    db=Depends(get_db),
):
    try:
        return spatial.parcels_geojson(db, bbox=bbox, period=period)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{parcel_id}", summary="地块详情")
def get_parcel(parcel_id: int, db=Depends(get_db)):
    data = spatial.get_parcel(parcel_id, db)
    if not data:
        raise HTTPException(status_code=404, detail="地块不存在")
    return data


@router.post("", summary="新建地块", status_code=201)
def create_parcel(body: ParcelCreate, db=Depends(get_db)):
    try:
        return spatial.create_parcel(body.model_dump(), db)
    except spatial.DuplicateCodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/{parcel_id}", summary="更新地块")
def update_parcel(parcel_id: int, body: ParcelUpdate, db=Depends(get_db)):
    data = spatial.update_parcel(parcel_id, body.model_dump(exclude_unset=True), db)
    if not data:
        raise HTTPException(status_code=404, detail="地块不存在")
    return data


@router.delete("/{parcel_id}", summary="删除地块（锁定后不可删除）", status_code=204)
def delete_parcel(parcel_id: int, db=Depends(get_db)):
    try:
        ok = spatial.delete_parcel(parcel_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail="地块不存在")


@router.post("/batch-delete", summary="批量删除地块（跳过锁定项）")
def batch_delete_parcels(body: BatchIdsBody, db=Depends(get_db)):
    return spatial.batch_delete_parcels(body.ids, db)


@router.post("/{parcel_id}/lock", summary="锁定 / 解锁地块（锁定后不可删除）")
def lock_parcel(parcel_id: int, body: LockBody, db=Depends(get_db)):
    data = spatial.set_parcel_locked(parcel_id, body.locked, db)
    if not data:
        raise HTTPException(status_code=404, detail="地块不存在")
    return {"id": parcel_id, "locked": body.locked}


@router.post("/batch-set-period", summary="批量设置期次（数据修复：为无期次地块标注）")
def batch_set_period(period: str = Query(..., description="base / current"),
                     ids: Optional[str] = Query(None, description="地块 id 逗号分隔（缺省=全部）"),
                     db=Depends(get_db)):
    if period not in ("base", "current"):
        raise HTTPException(status_code=422, detail="period 必须为 base 或 current")
    parcel_ids = [int(x) for x in ids.split(",")] if ids else None
    return spatial.set_parcels_period(parcel_ids, period, db)


@router.post("/import-shp", summary="导入 SHP 地块（zip：.shp/.shx/.dbf/.prj，关联项目与期次）")
async def import_shp(
    file: UploadFile = File(..., description="SHP 压缩包（WGS84/EPSG:4326）"),
    name_field: Optional[str] = Form(None, description="名称字段（可自动识别）"),
    land_use_field: Optional[str] = Form(None, description="用地性质字段（可自动识别）"),
    region_field: Optional[str] = Form(None, description="行政区名称字段（可自动识别）"),
    region_code: Optional[str] = Form(None, description="行政区划代码（如 420111）"),
    period: Optional[str] = Form("base", description="期次：base（基期）/ current（末期）"),
    project_id: Optional[int] = Form(None, description="所属分析项目 id"),
    db=Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="请上传 zip 压缩包（含 .shp/.shx/.dbf/.prj）")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422,
                            detail=f"压缩包超过 {settings.max_upload_mb}MB 上限")
    try:
        return shp_import.import_parcels_from_zip(
            content, db, name_field=name_field, land_use_field=land_use_field,
            region_field=region_field, region_code=region_code,
            period=period, project_id=project_id,
        )
    except (shp_import.ShpImportError, ValueError) as exc:
        import logging
        logging.getLogger("landvision.shp_import").warning("地块 SHP 导入被拒绝：%s", exc)
        raise HTTPException(status_code=422, detail=str(exc))

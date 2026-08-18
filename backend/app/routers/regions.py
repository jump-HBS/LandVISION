# -*- coding: utf-8 -*-
"""路由组：行政区划 regions —— 省/市/县 查询、GeoJSON、定位、SHP 导入。"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from ..config import settings
from ..database import get_db
from ..services import regions as regions_service
from ..services import shp_import

router = APIRouter(prefix="/regions", tags=["行政区划"])


@router.get("", summary="行政区列表（省/市/县）")
def list_regions(
    level: Optional[str] = Query(None, description="province / city / county"),
    parent_code: Optional[str] = Query(None, description="上级行政区划代码"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db=Depends(get_db),
):
    return regions_service.list_regions(db, level=level, parent_code=parent_code,
                                        page=page, page_size=page_size)


@router.get("/geojson", summary="行政区 GeoJSON（地图渲染）")
def regions_geojson(
    code: Optional[str] = Query(None, description="为空返回全部省级；有值返回其直接下级"),
    db=Depends(get_db),
):
    return regions_service.regions_geojson(db, code=code)


@router.get("/{code}", summary="行政区详情")
def get_region(code: str, db=Depends(get_db)):
    data = regions_service.get_region(code, db)
    if not data:
        raise HTTPException(status_code=404, detail="行政区不存在")
    return data


@router.get("/{code}/children", summary="行政区直接下级列表")
def region_children(code: str, db=Depends(get_db)):
    return regions_service.region_children(code, db)


@router.get("/{code}/locate", summary="行政区定位（中心点 + 包围盒）")
def region_locate(code: str, db=Depends(get_db)):
    data = regions_service.region_locate(code, db)
    if not data:
        raise HTTPException(status_code=404, detail="行政区不存在")
    return data


@router.post("/import", summary="导入市/县级行政区 SHP（zip：.shp/.shx/.dbf/.prj）")
async def import_regions(
    file: UploadFile = File(..., description="SHP 压缩包"),
    level: str = Form(..., description="province / city / county"),
    parent_code: Optional[str] = Form(None, description="上级代码（市/县必填）"),
    code_field: Optional[str] = Form(None, description="行政区代码字段名（可自动识别）"),
    name_field: Optional[str] = Form(None, description="行政区名称字段名（可自动识别）"),
    db=Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="请上传 zip 压缩包（含 .shp/.shx/.dbf/.prj）")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=422,
                            detail=f"压缩包超过 {settings.max_upload_mb}MB 上限")
    try:
        return shp_import.import_regions_from_zip(
            content, db, level=level, parent_code=parent_code,
            code_field=code_field, name_field=name_field,
        )
    except (shp_import.ShpImportError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

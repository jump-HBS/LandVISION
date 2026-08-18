# -*- coding: utf-8 -*-
"""路由组：兴趣点 pois —— 列表 / GeoJSON / CRUD / 批量删除。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..schemas import BatchIdsBody, PoiCreate, PoiUpdate
from ..services import spatial

router = APIRouter(prefix="/pois", tags=["兴趣点"])


@router.get("", summary="POI 分页列表")
def list_pois(
    poi_type: Optional[str] = Query(None, description="按类型过滤：交通/商业/教育/医疗/休闲"),
    bbox: Optional[str] = Query(None, description="视野范围 minx,miny,maxx,maxy"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    try:
        return spatial.list_pois(db, poi_type=poi_type, bbox=bbox,
                                 page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/geojson", summary="POI GeoJSON（地图渲染）")
def pois_geojson(
    bbox: Optional[str] = Query(None, description="视野范围 minx,miny,maxx,maxy"),
    db=Depends(get_db),
):
    try:
        return spatial.pois_geojson(db, bbox=bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("", summary="新建 POI", status_code=201)
def create_poi(body: PoiCreate, db=Depends(get_db)):
    return spatial.create_poi(body.model_dump(), db)


@router.delete("/{poi_id}", summary="删除 POI", status_code=204)
def delete_poi(poi_id: int, db=Depends(get_db)):
    try:
        ok = spatial.delete_poi(poi_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail="POI 不存在")


@router.post("/batch-delete", summary="批量删除 POI（跳过锁定项）")
def batch_delete_pois(body: BatchIdsBody, db=Depends(get_db)):
    return spatial.batch_delete_pois(body.ids, db)

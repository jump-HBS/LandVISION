# -*- coding: utf-8 -*-
"""路由组：地图标注 map_features —— 地图上绘制的点/线/面持久化，支持锁定与批量删除。"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..schemas import BatchIdsBody, LockBody, MapFeatureCreate
from ..services import map_features

router = APIRouter(prefix="/map-features", tags=["地图标注"])


@router.get("", summary="标注列表（按项目过滤）")
def list_features(project_id: Optional[int] = Query(None, description="所属分析项目 id"),
                  db=Depends(get_db)):
    return map_features.list_features(db, project_id=project_id)


@router.get("/geojson", summary="标注 GeoJSON（地图渲染）")
def features_geojson(project_id: Optional[int] = Query(None), db=Depends(get_db)):
    return map_features.features_geojson(db, project_id=project_id)


@router.post("", summary="保存地图绘制（点/线/面入库）", status_code=201)
def create_feature(body: MapFeatureCreate, db=Depends(get_db)):
    try:
        return map_features.create_feature(body.model_dump(), db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{feature_id}", summary="删除标注（锁定后不可删除）", status_code=204)
def delete_feature(feature_id: int, db=Depends(get_db)):
    try:
        ok = map_features.delete_feature(feature_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=404, detail="标注不存在")


@router.post("/batch-delete", summary="批量删除标注（跳过锁定项）")
def batch_delete(body: BatchIdsBody, db=Depends(get_db)):
    return map_features.batch_delete_features(body.ids, db)


@router.post("/{feature_id}/lock", summary="锁定 / 解锁标注")
def lock_feature(feature_id: int, body: LockBody, db=Depends(get_db)):
    data = map_features.set_locked(feature_id, body.locked, db)
    if not data:
        raise HTTPException(status_code=404, detail="标注不存在")
    return {"id": feature_id, "locked": body.locked}

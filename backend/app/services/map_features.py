# -*- coding: utf-8 -*-
"""
地图标注服务：地图上绘制的点/线/面（测量/勾绘）持久化到 map_features 表。

支持：按项目过滤、锁定（锁定后不可删除）、批量删除。
"""
import json
from typing import Optional

from shapely.geometry import mapping, shape

from .. import demo_data
from .spatial import is_demo

FEATURE_TYPES = ("point", "line", "polygon")


def _feature_out(f: dict) -> dict:
    return {
        "id": f["id"], "name": f["name"], "feature_type": f["feature_type"],
        "category": f.get("category"), "project_id": f.get("project_id"),
        "locked": f.get("locked", False), "properties": f.get("properties_json"),
        "geometry": f.get("geometry"),
    }


def list_features(db=None, project_id: Optional[int] = None) -> list:
    if is_demo():
        return [_feature_out(f) for f in demo_data.MAP_FEATURES
                if project_id is None or f.get("project_id") == project_id]
    from ..models import MapFeature
    from geoalchemy2.shape import to_shape
    q = db.query(MapFeature)
    if project_id:
        q = q.filter(MapFeature.project_id == project_id)
    return [
        {"id": r.id, "name": r.name, "feature_type": r.feature_type,
         "category": r.category, "project_id": r.project_id, "locked": r.locked,
         "properties": r.properties_json, "geometry": mapping(to_shape(r.geom))}
        for r in q.order_by(MapFeature.id).all()
    ]


def features_geojson(db=None, project_id: Optional[int] = None) -> dict:
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {
            "id": f["id"], "name": f["name"], "feature_type": f["feature_type"],
            "category": f["category"], "project_id": f["project_id"],
            "locked": f["locked"], "properties": f["properties"]}}
        for f in list_features(db, project_id=project_id)
    ]
    return {"type": "FeatureCollection", "features": features, "count": len(features)}


def create_feature(data: dict, db=None) -> dict:
    if data["feature_type"] not in FEATURE_TYPES:
        raise ValueError("feature_type 必须为 point / line / polygon")
    geom_type = {"point": "Point", "line": "LineString", "polygon": "Polygon"}[data["feature_type"]]
    if data["geometry"].get("type") != geom_type:
        raise ValueError(f"几何类型必须为 {geom_type}")
    if is_demo():
        pid = demo_data.next_id(demo_data.MAP_FEATURES)
        new = {
            "id": pid, "name": data["name"], "feature_type": data["feature_type"],
            "category": data.get("category"), "project_id": data.get("project_id"),
            "properties_json": data.get("properties") or {}, "locked": False,
            "geometry": data["geometry"],
        }
        demo_data.MAP_FEATURES.append(new)
        return _feature_out(new)
    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import MapFeature
    row = MapFeature(
        name=data["name"], feature_type=data["feature_type"],
        category=data.get("category"), project_id=data.get("project_id"),
        properties_json=data.get("properties") or {},
        geom=ST_GeomFromGeoJSON(json.dumps(data["geometry"])),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "feature_type": row.feature_type,
            "category": row.category, "project_id": row.project_id,
            "locked": row.locked, "properties": row.properties_json}


def _get(db, feature_id: int):
    if is_demo():
        return next((f for f in demo_data.MAP_FEATURES if f["id"] == feature_id), None)
    from ..models import MapFeature
    return db.query(MapFeature).filter(MapFeature.id == feature_id).first()


def delete_feature(feature_id: int, db=None) -> bool:
    if is_demo():
        f = _get(db, feature_id)
        if not f:
            return False
        if f.get("locked"):
            raise ValueError(f"标注已锁定，解除锁定后才能删除：{f['name']}")
        demo_data.MAP_FEATURES.remove(f)
        return True
    row = _get(db, feature_id)
    if not row:
        return False
    if row.locked:
        raise ValueError(f"标注已锁定，解除锁定后才能删除：{row.name}")
    db.delete(row)
    db.commit()
    return True


def batch_delete_features(feature_ids: list, db=None) -> dict:
    deleted, locked, missing = [], [], []
    for fid in feature_ids:
        f = _get(db, fid)
        if not f:
            missing.append(fid)
            continue
        name = f["name"] if is_demo() else f.name
        is_locked = f.get("locked") if is_demo() else f.locked
        if is_locked:
            locked.append({"id": fid, "name": name})
            continue
        delete_feature(fid, db)
        deleted.append(fid)
    return {"deleted": deleted, "locked": locked, "missing": missing}


def set_locked(feature_id: int, locked: bool, db=None) -> Optional[dict]:
    if is_demo():
        f = _get(db, feature_id)
        if not f:
            return None
        f["locked"] = locked
        return _feature_out(f)
    row = _get(db, feature_id)
    if not row:
        return None
    row.locked = locked
    db.commit()
    db.refresh(row)
    return {"id": row.id, "locked": row.locked}

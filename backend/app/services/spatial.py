# -*- coding: utf-8 -*-
"""
空间查询服务（模块一/二/三的核心）：视野查询、GeoJSON 序列化、地块/POI 的增删改查。

底层逻辑（对照《项目实现框架.md》第三节）：
  * Demo 模式：GeoJSON → shapely 对象 → 空间判断（相交/距离/缓冲）
  * POSTGIS 模式：把同样的空间逻辑写成 ST_* SQL，交给数据库执行

两种模式对外输出的数据结构完全一致，前端无感知。
"""
import json
import math
from typing import Optional

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from ..config import settings
from .. import demo_data

# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def is_demo() -> bool:
    """当前是否 Demo 模式（由 main.py 启动时决定）。"""
    return settings.runtime_demo_mode


def parse_bbox(bbox_str: str) -> tuple[float, float, float, float]:
    """解析 'minx,miny,maxx,maxy' 字符串为元组，并校验合法性。"""
    parts = [float(x) for x in bbox_str.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox 格式应为 minx,miny,maxx,maxy")
    minx, miny, maxx, maxy = parts
    if minx >= maxx or miny >= maxy:
        raise ValueError("bbox 范围非法：minx<maxx 且 miny<maxy")
    return minx, miny, maxx, maxy


def meters_per_degree(lat: float) -> tuple[float, float]:
    """纬度 lat 处，1° 经度/纬度对应的米数（等距圆柱近似，教学够用）。"""
    lon_scale = 111320.0 * math.cos(math.radians(lat))
    lat_scale = 110540.0
    return lon_scale, lat_scale


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """两点间球面近似距离（米）。与 PostGIS 的 ST_Distance(::geography) 结果接近。"""
    lon_scale, lat_scale = meters_per_degree((lat1 + lat2) / 2)
    dx = (lon2 - lon1) * lon_scale
    dy = (lat2 - lat1) * lat_scale
    return math.hypot(dx, dy)


def buffer_geojson(geometry: dict, radius_m: float) -> dict:
    """对 GeoJSON 几何做半径 radius_m 米的缓冲区，返回 GeoJSON。

    Demo 模式用 shapely 近似（米→度）。
    """
    g = shape(geometry)
    lon_scale, _ = meters_per_degree(g.centroid.y)
    deg = radius_m / lon_scale  # 米 → 度（按中心纬度近似）
    return mapping(g.buffer(deg))


def geometry_area_sqm(geometry: dict) -> float:
    """按几何计算面积（平方米）。

    经纬度 → 等距圆柱近似投影（按几何中心纬度缩放），再做鞋带公式。
    与 PostGIS 的 ST_Area(ST_Transform(geom, 3857)) 结果偏差在 1% 内，
    用于 SHP 导入/手工新建时自动补面积（与种子生成器口径一致）。
    """
    g = shape(geometry)
    lon_scale, lat_scale = meters_per_degree(g.centroid.y)
    ring = list(g.exterior.coords)
    area = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * lon_scale, ring[i][1] * lat_scale
        x2, y2 = ring[i + 1][0] * lon_scale, ring[i + 1][1] * lat_scale
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


# ---------------------------------------------------------------------------
# 地块 parcels
# ---------------------------------------------------------------------------

def _demo_find(items, item_id):
    for it in items:
        if it["id"] == item_id:
            return it
    return None


def list_parcels(db=None, bbox: Optional[str] = None, land_use: Optional[str] = None,
                 q: Optional[str] = None, district: Optional[str] = None,
                 region_code: Optional[str] = None, period: Optional[str] = None,
                 page: int = 1, page_size: int = 20) -> dict:
    """地块分页列表（不含几何，供表格展示）。bbox 非空时为视野范围查询。

    period：按期次过滤（base/current/None=全部）。
    region_code：按行政区划代码精确过滤（如 420111）。
    返回统一分页结构 {items, total, page, page_size, pages}。
    """
    from ..schemas import paginated

    if is_demo():
        result = []
        for p in demo_data.PARCELS:
            if bbox and not _demo_geom_in_bbox(p["geometry"], bbox):
                continue
            if land_use and p["land_use"] != land_use:
                continue
            if district and p.get("district") != district:
                continue
            if region_code and p.get("region_code") != region_code:
                continue
            if period and p.get("period") != period:
                continue
            if q and q not in p["name"] and q not in p["parcel_code"]:
                continue
            result.append(_parcel_summary(p))
        total = len(result)
        start = (page - 1) * page_size
        return paginated(result[start:start + page_size], page, page_size, total)

    from ..models import Parcel
    query = db.query(Parcel)
    if bbox:
        minx, miny, maxx, maxy = parse_bbox(bbox)
        from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope
        query = query.filter(
            ST_Intersects(Parcel.geom, ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))
        )
    if land_use:
        query = query.filter(Parcel.land_use == land_use)
    if district:
        query = query.filter(Parcel.district == district)
    if region_code:
        query = query.filter(Parcel.region_code == region_code)
    if period:
        query = query.filter(Parcel.period == period)
    if q:
        query = query.filter(Parcel.name.contains(q))
    total = query.count()
    rows = query.order_by(Parcel.id).offset((page - 1) * page_size).limit(page_size).all()
    return paginated([_parcel_summary_row(r) for r in rows], page, page_size, total)


def parcels_geojson(db=None, bbox: Optional[str] = None,
                    period: Optional[str] = None) -> dict:
    """地块 GeoJSON FeatureCollection（地图渲染用，可按期次过滤）。"""
    if is_demo():
        features = demo_data.parcel_features()
        if period:
            features = [f for f in features if f["properties"].get("period") == period]
        if bbox:
            features = [f for f in features if _demo_geom_in_bbox(f["geometry"], bbox)]
        return {"type": "FeatureCollection", "features": features}

    from ..models import Parcel
    from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope
    query = db.query(Parcel)
    if period:
        query = query.filter(Parcel.period == period)
    if bbox:
        minx, miny, maxx, maxy = parse_bbox(bbox)
        query = query.filter(
            ST_Intersects(Parcel.geom, ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))
        )
    features = [_parcel_feature_row(r) for r in query.all()]
    return {"type": "FeatureCollection", "features": features}


def get_parcel(parcel_id: int, db=None) -> Optional[dict]:
    """地块详情（含几何 GeoJSON）。"""
    if is_demo():
        p = _demo_find(demo_data.PARCELS, parcel_id)
        return dict(p) if p else None
    from ..models import Parcel
    row = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    return _parcel_detail_row(row) if row else None


def create_parcel(data: dict, db=None) -> dict:
    """新建地块。data 为 ParcelCreate 的 dict 形态（含 geometry GeoJSON）。

    面积缺失时按几何自动计算（SHP 导入/手工新建未填面积时兜底）。
    """
    # 面积兜底：未提供或为 0 → 按几何计算（等距圆柱近似，与种子口径一致）
    area = data.get("area_sqm")
    if not area:
        try:
            area = round(geometry_area_sqm(data["geometry"]), 2)
        except Exception:  # noqa: BLE001 —— 几何异常时保持 None，不阻断创建
            area = None

    # 编号唯一性校验（两种模式一致，返回 409 由路由层抛出）
    if is_demo():
        if any(p["parcel_code"] == data["parcel_code"] for p in demo_data.PARCELS):
            raise DuplicateCodeError(data["parcel_code"])
        pid = demo_data.next_id(demo_data.PARCELS)
        new = {
            "id": pid,
            "parcel_code": data["parcel_code"],
            "name": data["name"],
            "land_use": data["land_use"],
            "district": data.get("district"),
            "region_code": data.get("region_code"),
            "area_sqm": area,
            "far_limit": data.get("far_limit"),
            "height_limit": data.get("height_limit"),
            "period": data.get("period") or "base",
            "project_id": data.get("project_id"),
            "locked": data.get("locked", False),
            "created_at": None,
            "geometry": data["geometry"],
        }
        demo_data.PARCELS.append(new)
        return dict(new)

    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import Parcel
    if db.query(Parcel.id).filter(Parcel.parcel_code == data["parcel_code"]).first():
        raise DuplicateCodeError(data["parcel_code"])
    row = Parcel(
        parcel_code=data["parcel_code"],
        name=data["name"],
        land_use=data["land_use"],
        district=data.get("district"),
        region_code=data.get("region_code"),
        area_sqm=area,
        far_limit=data.get("far_limit"),
        height_limit=data.get("height_limit"),
        period=data.get("period") or "base",
        project_id=data.get("project_id"),
        locked=data.get("locked", False),
        geom=ST_GeomFromGeoJSON(json.dumps(data["geometry"])),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _parcel_detail_row(row)


def update_parcel(parcel_id: int, data: dict, db=None) -> Optional[dict]:
    # 几何更新且未显式提供面积 → 按新几何重算面积（保持数据一致）
    if data.get("geometry") and data.get("area_sqm") is None:
        try:
            data = {**data, "area_sqm": round(geometry_area_sqm(data["geometry"]), 2)}
        except Exception:  # noqa: BLE001
            pass

    if is_demo():
        p = _demo_find(demo_data.PARCELS, parcel_id)
        if not p:
            return None
        for key in ("name", "land_use", "district", "region_code",
                    "area_sqm", "far_limit", "height_limit", "geometry",
                    "period", "project_id", "locked"):
            if data.get(key) is not None:
                p[key] = data[key]
        return dict(p)

    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import Parcel
    row = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not row:
        return None
    for key in ("name", "land_use", "district", "region_code",
                "area_sqm", "far_limit", "height_limit",
                "period", "project_id", "locked"):
        if data.get(key) is not None:
            setattr(row, key, data[key])
    if data.get("geometry"):
        row.geom = ST_GeomFromGeoJSON(json.dumps(data["geometry"]))
    db.commit()
    db.refresh(row)
    return _parcel_detail_row(row)


def delete_parcel(parcel_id: int, db=None) -> bool:
    if is_demo():
        p = _demo_find(demo_data.PARCELS, parcel_id)
        if not p:
            return False
        if p.get("locked"):
            raise ValueError(f"地块已锁定，解除锁定后才能删除：{p['name']}")
        demo_data.PARCELS.remove(p)
        return True
    from ..models import Parcel
    row = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not row:
        return False
    if row.locked:
        raise ValueError(f"地块已锁定，解除锁定后才能删除：{row.name}")
    db.delete(row)
    db.commit()
    return True


def batch_delete_parcels(parcel_ids: list, db=None) -> dict:
    """批量删除地块（跳过锁定项）。"""
    deleted, locked, missing = [], [], []
    for pid in parcel_ids:
        parcel = get_parcel(pid, db)
        if not parcel:
            missing.append(pid)
            continue
        if parcel.get("locked"):
            locked.append({"id": pid, "name": parcel["name"]})
            continue
        delete_parcel(pid, db)
        deleted.append(pid)
    return {"deleted": deleted, "locked": locked, "missing": missing}


def set_parcel_locked(parcel_id: int, locked: bool, db=None) -> Optional[dict]:
    """锁定 / 解锁地块（锁定后不可删除）。"""
    if is_demo():
        p = _demo_find(demo_data.PARCELS, parcel_id)
        if not p:
            return None
        p["locked"] = locked
        return dict(p)
    from ..models import Parcel
    row = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not row:
        return None
    row.locked = locked
    db.commit()
    db.refresh(row)
    return _parcel_detail_row(row)


def set_parcels_period(parcel_ids: Optional[list], period: str, db=None) -> dict:
    """批量设置地块期次（数据修复：为无期次地块批量标注）。"""
    if is_demo():
        updated = 0
        for p in demo_data.PARCELS:
            if parcel_ids is None or p["id"] in parcel_ids:
                p["period"] = period
                updated += 1
        return {"updated": updated}
    from ..models import Parcel
    q = db.query(Parcel)
    if parcel_ids:
        q = q.filter(Parcel.id.in_(parcel_ids))
    updated = q.update({"period": period})
    db.commit()
    return {"updated": updated}


# ---------------------------------------------------------------------------
# 兴趣点 pois
# ---------------------------------------------------------------------------

def list_pois(db=None, poi_type: Optional[str] = None, bbox: Optional[str] = None,
              page: int = 1, page_size: int = 20) -> dict:
    """POI 分页列表，返回 {items, total, page, page_size, pages}。"""
    from ..schemas import paginated

    if is_demo():
        result = []
        for p in demo_data.POIS:
            if poi_type and p["poi_type"] != poi_type:
                continue
            if bbox and not _demo_geom_in_bbox(p["geometry"], bbox):
                continue
            result.append({"id": p["id"], "name": p["name"], "poi_type": p["poi_type"]})
        total = len(result)
        start = (page - 1) * page_size
        return paginated(result[start:start + page_size], page, page_size, total)

    from ..models import Poi
    from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope
    query = db.query(Poi)
    if poi_type:
        query = query.filter(Poi.poi_type == poi_type)
    if bbox:
        minx, miny, maxx, maxy = parse_bbox(bbox)
        query = query.filter(ST_Intersects(Poi.geom, ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)))
    total = query.count()
    rows = query.order_by(Poi.id).offset((page - 1) * page_size).limit(page_size).all()
    items = [{"id": r.id, "name": r.name, "poi_type": r.poi_type} for r in rows]
    return paginated(items, page, page_size, total)


def pois_geojson(db=None, bbox: Optional[str] = None) -> dict:
    if is_demo():
        features = demo_data.poi_features()
        if bbox:
            features = [f for f in features if _demo_geom_in_bbox(f["geometry"], bbox)]
        return {"type": "FeatureCollection", "features": features}

    from ..models import Poi
    from geoalchemy2.functions import ST_Intersects, ST_MakeEnvelope
    from geoalchemy2.shape import to_shape
    query = db.query(Poi)
    if bbox:
        minx, miny, maxx, maxy = parse_bbox(bbox)
        query = query.filter(ST_Intersects(Poi.geom, ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)))
    features = [
        {"type": "Feature", "geometry": mapping(to_shape(r.geom)),
         "properties": {"id": r.id, "name": r.name, "poi_type": r.poi_type}}
        for r in query.all()
    ]
    return {"type": "FeatureCollection", "features": features}


def create_poi(data: dict, db=None) -> dict:
    if is_demo():
        pid = demo_data.next_id(demo_data.POIS)
        new = {"id": pid, "name": data["name"], "poi_type": data["poi_type"],
               "project_id": data.get("project_id"), "period": data.get("period"),
               "locked": data.get("locked", False), "geometry": data["geometry"]}
        demo_data.POIS.append(new)
        return dict(new)

    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import Poi
    row = Poi(name=data["name"], poi_type=data["poi_type"],
              project_id=data.get("project_id"), period=data.get("period"),
              locked=data.get("locked", False),
              geom=ST_GeomFromGeoJSON(json.dumps(data["geometry"])))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "poi_type": row.poi_type,
            "project_id": row.project_id, "locked": row.locked}


def delete_poi(poi_id: int, db=None) -> bool:
    if is_demo():
        p = _demo_find(demo_data.POIS, poi_id)
        if not p:
            return False
        if p.get("locked"):
            raise ValueError(f"POI 已锁定，解除锁定后才能删除：{p['name']}")
        demo_data.POIS.remove(p)
        return True
    from ..models import Poi
    row = db.query(Poi).filter(Poi.id == poi_id).first()
    if not row:
        return False
    if row.locked:
        raise ValueError(f"POI 已锁定，解除锁定后才能删除：{row.name}")
    db.delete(row)
    db.commit()
    return True


def batch_delete_pois(poi_ids: list, db=None) -> dict:
    """批量删除 POI（跳过锁定项）。"""
    deleted, locked, missing = [], [], []
    for pid in poi_ids:
        p = None
        if is_demo():
            p = _demo_find(demo_data.POIS, pid)
            if p:
                if p.get("locked"):
                    locked.append({"id": pid, "name": p["name"]})
                    continue
                demo_data.POIS.remove(p)
                deleted.append(pid)
            else:
                missing.append(pid)
            continue
        from ..models import Poi
        row = db.query(Poi).filter(Poi.id == pid).first()
        if not row:
            missing.append(pid)
            continue
        if row.locked:
            locked.append({"id": pid, "name": row.name})
            continue
        db.delete(row)
        deleted.append(pid)
    if not is_demo():
        db.commit()
    return {"deleted": deleted, "locked": locked, "missing": missing}


# ---------------------------------------------------------------------------
# 内部辅助：记录 → 输出结构
# ---------------------------------------------------------------------------

class DuplicateCodeError(Exception):
    """地块编号重复（业务异常，路由层转成 409）。"""

    def __init__(self, parcel_code: str):
        super().__init__(f"地块编号已存在：{parcel_code}")
        self.parcel_code = parcel_code


def _demo_geom_in_bbox(geometry: dict, bbox: str) -> bool:
    minx, miny, maxx, maxy = parse_bbox(bbox)
    return shape(geometry).intersects(box(minx, miny, maxx, maxy))


def _fmt_date(d) -> str | None:
    return d.strftime("%Y-%m-%d") if d else None


def _parcel_summary(p: dict) -> dict:
    return {
        "id": p["id"], "parcel_code": p["parcel_code"], "name": p["name"],
        "land_use": p["land_use"], "district": p.get("district"),
        "region_code": p.get("region_code"),
        "period": p.get("period"), "project_id": p.get("project_id"),
        "locked": p.get("locked", False),
        "area_sqm": p["area_sqm"], "far_limit": p["far_limit"],
        "height_limit": p["height_limit"],
        "created_at": p.get("created_at"),
    }


def _parcel_summary_row(r) -> dict:
    return {
        "id": r.id, "parcel_code": r.parcel_code, "name": r.name,
        "land_use": r.land_use, "district": r.district,
        "region_code": r.region_code,
        "period": r.period, "project_id": r.project_id, "locked": r.locked,
        "area_sqm": float(r.area_sqm) if r.area_sqm is not None else None,
        "far_limit": float(r.far_limit) if r.far_limit is not None else None,
        "height_limit": float(r.height_limit) if r.height_limit is not None else None,
        "created_at": _fmt_date(r.created_at),
    }


def _parcel_feature_row(r) -> dict:
    from geoalchemy2.shape import to_shape
    return {
        "type": "Feature",
        "geometry": mapping(to_shape(r.geom)),
        "properties": _parcel_summary_row(r),
    }


def _parcel_detail_row(r) -> dict:
    from geoalchemy2.shape import to_shape
    d = _parcel_summary_row(r)
    d["geometry"] = mapping(to_shape(r.geom))
    return d

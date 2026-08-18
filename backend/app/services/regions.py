# -*- coding: utf-8 -*-
"""
行政区划服务：国家 - 省 - 市 - 县 四级查询、GeoJSON 输出、定位。

数据来源：
  * 国家（虚拟根节点）：code=100000，name=中国
  * 省级（34 个）：内置数据（Demo 内存 / database/03_regions.sql 入库）
  * 市级 / 县级：中国_县.geojson 转换产物
      - Demo 模式：首次请求时懒加载 backend/app/data/china_regions.json
      - POSTGIS 模式：由 tools/load_regions_pg.py 导入 regions 表
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from ..schemas import paginated
from .. import demo_data
from .spatial import is_demo

COUNTRY = {"code": "100000", "name": "中国", "level": "country", "parent_code": None}

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "china_regions.json"


@lru_cache(maxsize=1)
def _load_sub_regions() -> tuple:
    """懒加载市/县级数据（demo 模式）。返回 (cities, counties)。"""
    if not _DATA_FILE.exists():
        return (), ()
    with open(_DATA_FILE, encoding="utf-8") as f:
        payload = json.load(f)
    return tuple(payload.get("cities", ())), tuple(payload.get("counties", ()))


def _all_demo_regions() -> list:
    """Demo 模式全部行政区 = 省级（内置）+ 市 + 县（懒加载）。"""
    cities, counties = _load_sub_regions()
    return list(demo_data.REGIONS) + list(cities) + list(counties)


def _country_children(db=None) -> list:
    """国家（100000）的直接下级 = 34 个省级。"""
    if is_demo():
        return sorted(
            [_region_summary(r) for r in demo_data.REGIONS], key=lambda x: x["code"]
        )
    from ..models import Region
    rows = db.query(Region).filter(Region.level == "province").order_by(Region.code).all()
    return [_region_summary_row(r) for r in rows]


def list_regions(db=None, level: Optional[str] = None,
                 parent_code: Optional[str] = None,
                 page: int = 1, page_size: int = 50) -> dict:
    """行政区列表（按层级/上级代码过滤，分页）。"""
    if is_demo():
        result = []
        for r in _all_demo_regions():
            if level and r["level"] != level:
                continue
            if parent_code and r.get("parent_code") != parent_code:
                continue
            result.append(_region_summary(r))
        result.sort(key=lambda r: r["code"])
        total = len(result)
        start = (page - 1) * page_size
        return paginated(result[start:start + page_size], page, page_size, total)

    from ..models import Region
    query = db.query(Region)
    if level:
        query = query.filter(Region.level == level)
    if parent_code:
        query = query.filter(Region.parent_code == parent_code)
    total = query.count()
    rows = query.order_by(Region.code).offset((page - 1) * page_size).limit(page_size).all()
    return paginated([_region_summary_row(r) for r in rows], page, page_size, total)


def region_children(code: str, db=None) -> list:
    """某行政区的直接下级（100000 → 省级）。"""
    if code == "100000":
        return _country_children(db)

    if is_demo():
        children = [r for r in _all_demo_regions() if r.get("parent_code") == code]
        return sorted([_region_summary(r) for r in children], key=lambda r: r["code"])

    from ..models import Region
    rows = db.query(Region).filter(Region.parent_code == code).order_by(Region.code).all()
    return [_region_summary_row(r) for r in rows]


def get_region(code: str, db=None) -> Optional[dict]:
    if code == "100000":
        return dict(COUNTRY)
    if is_demo():
        r = next((x for x in _all_demo_regions() if x["code"] == code), None)
        return dict(r) if r else None
    from ..models import Region
    row = db.query(Region).filter(Region.code == code).first()
    return _region_detail_row(row) if row else None


def regions_geojson(db=None, code: Optional[str] = None) -> dict:
    """行政区 GeoJSON。

    code 为空或 100000 → 全部省级；其余返回该行政区直接下级
    （无下级则返回自身几何，供边界展示）。
    """
    if is_demo():
        if not code or code == "100000":
            features = demo_data.region_features()
        else:
            children = [r for r in _all_demo_regions() if r.get("parent_code") == code]
            if children:
                features = [_region_feature(r) for r in children if r.get("geometry")]
            else:
                own = [r for r in _all_demo_regions() if r["code"] == code]
                features = [_region_feature(r) for r in own if r.get("geometry")]
        return {"type": "FeatureCollection", "features": features}

    from ..models import Region
    if not code or code == "100000":
        rows = db.query(Region).filter(Region.level == "province").all()
    else:
        children = db.query(Region).filter(Region.parent_code == code).all()
        rows = children if children else db.query(Region).filter(Region.code == code).all()
    return {"type": "FeatureCollection", "features": [_region_feature_row(r) for r in rows]}


def _bbox_of(geoms: list) -> tuple | None:
    """多几何包围盒合并（逐要素 bounds 取极值，避免 unary_union 的拓扑校验）。"""
    bounds_list = [g.bounds for g in geoms if not g.is_empty]
    if not bounds_list:
        return None
    return (min(b[0] for b in bounds_list), min(b[1] for b in bounds_list),
            max(b[2] for b in bounds_list), max(b[3] for b in bounds_list))


def region_locate(code: str, db=None) -> Optional[dict]:
    """行政区定位：返回几何中心与包围盒（前端飞行定位 + fitBounds 用）。

    无几何的行政区（如市级未存几何）由子级几何的包围盒推导。
    """
    if code == "100000":
        if is_demo():
            gs = [shape(r["geometry"]) for r in demo_data.REGIONS]
            bbox = _bbox_of(gs)
            if bbox:
                minx, miny, maxx, maxy = bbox
                return {"code": code, "name": "中国", "level": "country",
                        "center": [(minx + maxx) / 2, (miny + maxy) / 2],
                        "bbox": [round(v, 6) for v in bbox]}

    if is_demo():
        r = next((x for x in _all_demo_regions() if x["code"] == code), None)
        if not r:
            return None
        if r.get("geometry"):
            g = shape(r["geometry"])
        else:
            children = [x for x in _all_demo_regions()
                        if x.get("parent_code") == code and x.get("geometry")]
            if not children:
                return {"code": r["code"], "name": r["name"], "level": r["level"],
                        "center": None, "bbox": None}
            bbox = _bbox_of([shape(c["geometry"]) for c in children])
            return {"code": r["code"], "name": r["name"], "level": r["level"],
                    "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
                    "bbox": [round(v, 6) for v in bbox]}
        minx, miny, maxx, maxy = g.bounds
        c = g.centroid
        return {"code": r["code"], "name": r["name"], "level": r["level"],
                "center": [round(c.x, 6), round(c.y, 6)],
                "bbox": [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)]}

    from geoalchemy2.shape import to_shape
    from ..models import Region
    row = db.query(Region).filter(Region.code == code).first()
    if not row:
        return None
    if row.geom is not None:
        g = to_shape(row.geom)
        return {"code": row.code, "name": row.name, "level": row.level,
                "center": [round(g.centroid.x, 6), round(g.centroid.y, 6)],
                "bbox": [round(v, 6) for v in g.bounds]}
    children = db.query(Region).filter(Region.parent_code == code,
                                       Region.geom.isnot(None)).all()
    if not children:
        return {"code": row.code, "name": row.name, "level": row.level,
                "center": None, "bbox": None}
    bbox = _bbox_of([to_shape(c.geom) for c in children])
    return {"code": row.code, "name": row.name, "level": row.level,
            "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
            "bbox": [round(v, 6) for v in bbox]}


def import_regions(features: list, level: str, parent_code: Optional[str] = None,
                   db=None) -> dict:
    """批量导入行政区要素（SHP 解析后的 features）。"""
    if level not in ("province", "city", "county"):
        raise ValueError("level 必须为 province / city / county")
    if level != "province" and not parent_code:
        raise ValueError("导入市级/县级行政区必须提供 parent_code")

    imported, skipped = 0, []
    for f in features:
        props = f["properties"]
        code = str(props.get("code") or "").strip()
        name = str(props.get("name") or "").strip()
        if not code or not name:
            skipped.append({"reason": "缺少行政区代码或名称", "name": name or code})
            continue
        geom = _to_multipolygon(f["geometry"])
        if is_demo():
            if any(r["code"] == code for r in _all_demo_regions()):
                skipped.append({"reason": f"代码重复：{code}", "name": name})
                continue
            demo_data.REGIONS.append({
                "code": code, "name": name, "level": level,
                "parent_code": parent_code or "100000", "geometry": geom,
            })
            imported += 1
        else:
            from geoalchemy2.functions import ST_GeomFromGeoJSON
            from ..models import Region
            if db.query(Region.id).filter(Region.code == code).first():
                skipped.append({"reason": f"代码重复：{code}", "name": name})
                continue
            db.add(Region(code=code, name=name, level=level,
                          parent_code=parent_code or "100000",
                          geom=ST_GeomFromGeoJSON(json.dumps(geom))))
            imported += 1
    if not is_demo():
        db.commit()
    return {"imported": imported, "skipped": skipped}


def _to_multipolygon(geom: dict) -> dict:
    if geom["type"] == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
    return geom


def _region_summary(r: dict) -> dict:
    return {"code": r["code"], "name": r["name"], "level": r["level"],
            "parent_code": r.get("parent_code")}


def _region_summary_row(r) -> dict:
    return {"code": r.code, "name": r.name, "level": r.level, "parent_code": r.parent_code}


def _region_feature(r: dict) -> dict:
    return {"type": "Feature", "geometry": r["geometry"], "properties": _region_summary(r)}


def _region_feature_row(r) -> dict:
    from geoalchemy2.shape import to_shape
    return {"type": "Feature", "geometry": mapping(to_shape(r.geom)),
            "properties": _region_summary_row(r)}


def _region_detail_row(r) -> dict:
    from geoalchemy2.shape import to_shape
    d = _region_summary_row(r)
    d["geometry"] = mapping(to_shape(r.geom)) if r.geom is not None else None
    return d

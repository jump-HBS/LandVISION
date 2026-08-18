# -*- coding: utf-8 -*-
"""
空间分析服务（v2.0）：转移矩阵 / 适宜性评价 / 可达性分析（模块一~三）+ 结果持久化。

设计：
  * 核心算法统一用 shapely 实现，数据获取按 Demo/PG 模式分支，两种模式结果一致；
  * 分析范围通过 projects.resolve_project_scope 统一解析（继承项目范围 + 子集校验）；
  * 三模块结果分别持久化到 land_change_patches / suitability_grids / accessibility_results，
    供驾驶舱统筹、报告生成与模块间联动直接查询，避免重复计算。
"""
import json
import math
from typing import Optional

from shapely.geometry import Point, shape
from shapely.ops import unary_union

from ..config import settings
from .. import demo_data
from .spatial import is_demo
from .projects import resolve_project_scope

# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------

def _area_m2(geom) -> float:
    """shapely 几何面积（度²）→ 平方米（等距圆柱近似）。"""
    if geom.is_empty:
        return 0.0
    lon_scale = 111320.0 * math.cos(math.radians(geom.centroid.y))
    lat_scale = 110540.0
    return abs(geom.area) * lon_scale * lat_scale


def _load_parcels(db, period: Optional[str] = None) -> list:
    """加载地块（含 shapely 几何）。period=None 时返回全部。"""
    if is_demo():
        src = demo_data.PARCELS
        return [
            {"id": p["id"], "parcel_code": p["parcel_code"], "name": p["name"],
             "land_use": p["land_use"], "area_sqm": p.get("area_sqm"),
             "period": p.get("period"), "project_id": p.get("project_id"),
             "locked": p.get("locked", False),
             "geom": shape(p["geometry"])}
            for p in src if period is None or p.get("period") == period
        ]
    from ..models import Parcel
    from geoalchemy2.shape import to_shape
    query = db.query(Parcel)
    if period:
        query = query.filter(Parcel.period == period)
    return [
        {"id": r.id, "parcel_code": r.parcel_code, "name": r.name,
         "land_use": r.land_use, "area_sqm": float(r.area_sqm) if r.area_sqm else None,
         "period": r.period, "project_id": r.project_id, "locked": r.locked,
         "geom": to_shape(r.geom)}
        for r in query.all()
    ]


def _load_pois(db) -> list:
    """加载 POI（含坐标）。"""
    if is_demo():
        return [{"name": p["name"], "poi_type": p["poi_type"],
                 "point": Point(p["geometry"]["coordinates"])} for p in demo_data.POIS]
    from ..models import Poi
    from geoalchemy2.shape import to_shape
    return [
        {"name": r.name, "poi_type": r.poi_type, "point": to_shape(r.geom)}
        for r in db.query(Poi).all()
    ]


def _load_zones(db) -> list:
    """加载三区三线控制线（含 shapely 几何）。"""
    if is_demo():
        return [{"zone_name": z["zone_name"], "zone_type": z["zone_type"],
                 "geom": shape(z["geometry"])} for z in demo_data.PLANNING_ZONES]
    from ..models import PlanningZone
    from geoalchemy2.shape import to_shape
    return [
        {"zone_name": r.zone_name, "zone_type": r.zone_type, "geom": to_shape(r.geom)}
        for r in db.query(PlanningZone).all()
    ]


def _scope_geom(scope: Optional[dict]):
    return shape(scope) if scope else None


# ---------------------------------------------------------------------------
# 结果持久化辅助
# ---------------------------------------------------------------------------

def _clear_patches(db, project_id: int):
    if is_demo():
        demo_data.LAND_CHANGE_PATCHES[:] = [
            p for p in demo_data.LAND_CHANGE_PATCHES if p.get("project_id") != project_id]
        return
    from ..models import LandChangePatch
    db.query(LandChangePatch).filter(LandChangePatch.project_id == project_id).delete()
    db.commit()


def _insert_patches(db, project_id: int, records: list) -> list:
    """写入图斑，返回与 records 同序的持久化 id 列表。"""
    ids = []
    if is_demo():
        pid0 = demo_data.next_id(demo_data.LAND_CHANGE_PATCHES)
        for i, rec in enumerate(records):
            demo_data.LAND_CHANGE_PATCHES.append({
                "id": pid0 + i, "project_id": project_id,
                "from_land_use": rec["from_land_use"], "to_land_use": rec["to_land_use"],
                "area_sqm": rec["area_sqm"], "change_type": rec["change_type"],
                "is_conflict": None, "geometry": rec["geometry"],
            })
            ids.append(pid0 + i)
        return ids
    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import LandChangePatch
    for rec in records:
        row = LandChangePatch(
            project_id=project_id,
            from_land_use=rec["from_land_use"], to_land_use=rec["to_land_use"],
            area_sqm=rec["area_sqm"], change_type=rec["change_type"],
            geom=ST_GeomFromGeoJSON(json.dumps(rec["geometry"])),
        )
        db.add(row)
        db.flush()
        ids.append(row.id)
    db.commit()
    return ids


def list_patches(db=None, project_id: Optional[int] = None) -> dict:
    """查询变化图斑（持久化数据，GeoJSON）。"""
    if is_demo():
        feats = [
            {"type": "Feature", "geometry": p["geometry"], "properties": {
                "id": p["id"], "project_id": p.get("project_id"),
                "from_land_use": p["from_land_use"], "to_land_use": p["to_land_use"],
                "area_sqm": p["area_sqm"], "change_type": p["change_type"],
                "is_conflict": p.get("is_conflict")}}
            for p in demo_data.LAND_CHANGE_PATCHES
            if project_id is None or p.get("project_id") == project_id
        ]
        return {"type": "FeatureCollection", "features": feats,
                "count": len(feats)}
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping
    from ..models import LandChangePatch
    q = db.query(LandChangePatch)
    if project_id:
        q = q.filter(LandChangePatch.project_id == project_id)
    rows = q.order_by(LandChangePatch.id).all()
    feats = [
        {"type": "Feature", "geometry": mapping(to_shape(r.geom)), "properties": {
            "id": r.id, "project_id": r.project_id,
            "from_land_use": r.from_land_use, "to_land_use": r.to_land_use,
            "area_sqm": float(r.area_sqm or 0), "change_type": r.change_type,
            "is_conflict": r.is_conflict}}
        for r in rows
    ]
    return {"type": "FeatureCollection", "features": feats, "count": len(feats)}


def _clear_grids(db, project_id: int):
    if is_demo():
        demo_data.SUITABILITY_GRIDS[:] = [
            g for g in demo_data.SUITABILITY_GRIDS if g.get("project_id") != project_id]
        return
    from ..models import SuitabilityGrid
    db.query(SuitabilityGrid).filter(SuitabilityGrid.project_id == project_id).delete()
    db.commit()


def list_grids(db=None, project_id: Optional[int] = None) -> dict:
    """查询适宜性评价格网（持久化数据，GeoJSON）。"""
    if is_demo():
        feats = [
            {"type": "Feature", "geometry": g["geometry"], "properties": {
                "id": g["id"], "project_id": g.get("project_id"),
                "score": g["score"], "level": g["level"],
                "factors": g.get("factors_json")}}
            for g in demo_data.SUITABILITY_GRIDS
            if project_id is None or g.get("project_id") == project_id
        ]
        return {"type": "FeatureCollection", "features": feats, "count": len(feats)}
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping
    from ..models import SuitabilityGrid
    q = db.query(SuitabilityGrid)
    if project_id:
        q = q.filter(SuitabilityGrid.project_id == project_id)
    rows = q.order_by(SuitabilityGrid.id).all()
    feats = [
        {"type": "Feature", "geometry": mapping(to_shape(r.geom)), "properties": {
            "id": r.id, "project_id": r.project_id,
            "score": float(r.score or 0), "level": r.level, "factors": r.factors_json}}
        for r in rows
    ]
    return {"type": "FeatureCollection", "features": feats, "count": len(feats)}


def _clear_accessibility(db, project_id: int):
    if is_demo():
        demo_data.ACCESSIBILITY_RESULTS[:] = [
            r for r in demo_data.ACCESSIBILITY_RESULTS if r.get("project_id") != project_id]
        return
    from ..models import AccessibilityResult
    db.query(AccessibilityResult).filter(AccessibilityResult.project_id == project_id).delete()
    db.commit()


def list_accessibility(db=None, project_id: Optional[int] = None) -> list:
    """查询可达性分析结果（持久化数据，最新在前）。"""
    if is_demo():
        return [
            {"id": r["id"], "project_id": r.get("project_id"),
             "facility_types": r.get("facility_types"), "radius_m": r.get("radius_m"),
             "parcel_total": r.get("parcel_total"), "covered_count": r.get("covered_count"),
             "coverage_rate": r.get("coverage_rate"), "gap_parcel_ids": r.get("gap_parcel_ids")}
            for r in reversed(demo_data.ACCESSIBILITY_RESULTS)
            if project_id is None or r.get("project_id") == project_id
        ]
    from ..models import AccessibilityResult
    q = db.query(AccessibilityResult)
    if project_id:
        q = q.filter(AccessibilityResult.project_id == project_id)
    return [
        {"id": r.id, "project_id": r.project_id, "facility_types": r.facility_types,
         "radius_m": float(r.radius_m or 0), "parcel_total": r.parcel_total,
         "covered_count": r.covered_count, "coverage_rate": float(r.coverage_rate or 0),
         "gap_parcel_ids": r.gap_parcel_ids}
        for r in q.order_by(AccessibilityResult.id.desc()).all()
    ]


# ===========================================================================
# 模块一：用地变化转移矩阵
# ===========================================================================

def transition_matrix(db, scope: Optional[dict] = None,
                      project_id: Optional[int] = None) -> dict:
    """两期用地叠加 → 转移矩阵 + 变化图斑（结果按项目持久化）。"""
    scope, _ = resolve_project_scope(db, project_id, scope)
    scope_g = _scope_geom(scope)
    base = _load_parcels(db, "base")
    current = _load_parcels(db, "current")
    if scope_g:
        base = [p for p in base if p["geom"].intersects(scope_g)]
        current = [p for p in current if p["geom"].intersects(scope_g)]
    if not base or not current:
        return {"rows": [], "summary": [], "changes_geojson": {"type": "FeatureCollection", "features": []},
                "base_count": len(base), "current_count": len(current),
                "hint": "缺少两期数据，请先导入基期/末期 SHP 或一键生成演示基期"}

    # 两两交集 → 按地类组合聚合
    from collections import defaultdict
    agg = defaultdict(float)
    for b in base:
        for c in current:
            inter = b["geom"].intersection(c["geom"])
            if not inter.is_empty and inter.area > 0:
                agg[(b["land_use"], c["land_use"])] += _area_m2(inter)

    # 消失（基期未保留）与新增（末期新出现）
    base_union = unary_union([p["geom"] for p in base])
    current_union = unary_union([p["geom"] for p in current])
    vanished_geom = base_union.difference(current_union)
    added_geom = current_union.difference(base_union)

    rows = []
    for (from_use, to_use), area in sorted(agg.items()):
        rows.append({"from_use": from_use, "to_use": to_use, "area_sqm": round(area, 2)})
    if not vanished_geom.is_empty:
        rows.append({"from_use": "（消失）", "to_use": "—", "area_sqm": round(_area_m2(vanished_geom), 2)})
    if not added_geom.is_empty:
        rows.append({"from_use": "—", "to_use": "（新增）", "area_sqm": round(_area_m2(added_geom), 2)})

    # 各类型面积变化汇总
    use_types = sorted({p["land_use"] for p in base + current})
    base_area = defaultdict(float)
    cur_area = defaultdict(float)
    for p in base:
        base_area[p["land_use"]] += p["area_sqm"] or _area_m2(p["geom"])
    for p in current:
        cur_area[p["land_use"]] += p["area_sqm"] or _area_m2(p["geom"])
    summary = [
        {"land_use": t,
         "base_area_sqm": round(base_area.get(t, 0), 2),
         "current_area_sqm": round(cur_area.get(t, 0), 2),
         "delta_sqm": round(cur_area.get(t, 0) - base_area.get(t, 0), 2)}
        for t in use_types
    ]

    # 变化图斑（地图渲染）+ 持久化
    from shapely.geometry import mapping
    patch_records = []   # 持久化记录
    changes = []         # 返回 GeoJSON（附 patch_id）
    def add_change(geom, kind, change_type, from_use, to_use):
        patch_records.append({
            "from_land_use": from_use, "to_land_use": to_use,
            "area_sqm": round(_area_m2(geom), 2),
            "change_type": change_type, "geometry": mapping(geom),
        })
        changes.append({"type": "Feature", "geometry": mapping(geom),
                        "properties": {"kind": kind, "change_type": change_type,
                                       "from_use": from_use, "to_use": to_use,
                                       "patch_id": None}})
    if not added_geom.is_empty:
        add_change(added_geom, "新增", "新增", None, None)
    if not vanished_geom.is_empty:
        add_change(vanished_geom, "消失", "拆除", None, None)
    for b in base:
        for c in current:
            inter = b["geom"].intersection(c["geom"])
            if not inter.is_empty and inter.area > 0 and b["land_use"] != c["land_use"]:
                add_change(inter, "转换",
                           "植被变化" if c["land_use"] in ("耕地", "园地", "林地", "草地")
                           else "新增建设", b["land_use"], c["land_use"])

    if project_id:
        _clear_patches(db, project_id)
        ids = _insert_patches(db, project_id, patch_records)
        for i, pid in enumerate(ids):
            changes[i]["properties"]["patch_id"] = pid

    return {
        "rows": rows,
        "summary": summary,
        "changes_geojson": {"type": "FeatureCollection", "features": changes},
        "base_count": len(base),
        "current_count": len(current),
        "persisted": project_id is not None,
    }


def import_period_parcels(db, zip_bytes: bytes, period: str,
                          name_field: str = None, land_use_field: str = None,
                          region_code: str = None, project_id: int = None) -> dict:
    """导入某期次地块 SHP（关联项目）。"""
    from .shp_import import import_parcels_from_zip
    result = import_parcels_from_zip(
        zip_bytes, db, name_field=name_field, land_use_field=land_use_field,
        region_field=None, region_code=region_code,
    )
    if is_demo():
        batch_codes = [f["parcel_code"] for f in _recent_imports_demo(result)]
        for p in demo_data.PARCELS:
            if p["parcel_code"] in batch_codes:
                p["period"] = period
                p["project_id"] = project_id
    else:
        from ..models import Parcel
        from .shp_import import _BATCH_SEQ
        batch = f"IMP-{_BATCH_SEQ[0]}-"
        rows = db.query(Parcel).filter(Parcel.parcel_code.like(f"{batch}%")).all()
        for r in rows:
            r.period = period
            r.project_id = project_id
        db.commit()
    result["period"] = period
    result["project_id"] = project_id
    return result


def _recent_imports_demo(result) -> list:
    return [p["parcel_code"] for p in demo_data.PARCELS[-result["imported"]:]] if result["imported"] else []


def generate_demo_base(db, project_id: int = None) -> dict:
    """一键生成演示基期数据：以现有未标记期次（period=None）的地块为末期，
    复制为基期并模拟三处变化。只处理未标记期次的地块：重复调用直接返回。"""
    current = [p for p in _load_parcels(db, None) if p.get("period") is None]
    if not current:
        return {"created": 0, "message": "所有地块均已标记期次，无需重复生成演示基期"}

    from shapely.affinity import translate

    created = 0
    for i, p in enumerate(current):
        if i == 5:
            continue  # 该地块仅在末期出现（基期不存在）→ 新增
        land_use = p["land_use"]
        geom = p["geom"]
        if i == 1:  # 基期是耕地，末期变为现状类型 → 类型转换
            land_use = "耕地"
        if i == 4:  # 基期地块向东偏移 → 局部消失（基期范围未保留）+ 局部新增
            geom = translate(geom, xoff=0.004, yoff=0.0)
        _insert_parcel(db, {
            "parcel_code": f"BASE-{p['parcel_code']}",
            "name": f"{p['name']}（基期）",
            "land_use": land_use,
            "district": None, "region_code": None,
            "area_sqm": None, "far_limit": None, "height_limit": None,
            "period": "base", "project_id": project_id,
            "geometry": _to_geojson(geom),
        })
        created += 1
    if is_demo():
        for p in demo_data.PARCELS:
            if p.get("period") is None:
                p["period"] = "current"
                if project_id:
                    p["project_id"] = project_id
    else:
        from ..models import Parcel
        db.query(Parcel).filter(Parcel.period.is_(None)).update(
            {"period": "current", **({"project_id": project_id} if project_id else {})})
        db.commit()
    return {"created": created, "message": f"演示基期已生成（{created} 宗），现有地块已标记为末期"}


def _insert_parcel(db, record: dict):
    from .spatial import create_parcel
    return create_parcel(record, db)


def _to_geojson(geom) -> dict:
    from shapely.geometry import mapping
    return mapping(geom)


# ===========================================================================
# 模块二：土地适宜性评价（多因子加权叠加，格网法 + 刚性约束）
# ===========================================================================

SUITABILITY_TARGETS = {
    "建设用地适宜性": {
        "factors": [
            {"key": "traffic", "name": "交通便利度", "default": 0.30},
            {"key": "service", "name": "公共服务配套", "default": 0.20},
            {"key": "eco", "name": "生态约束（负向）", "default": 0.30},
            {"key": "builtup", "name": "现状建成邻近", "default": 0.20},
        ],
    },
    "耕地适宜性": {
        "factors": [
            {"key": "water", "name": "水源邻近度", "default": 0.35},
            {"key": "flat", "name": "地形平缓度（模拟）", "default": 0.25},
            {"key": "service", "name": "耕作服务便利", "default": 0.20},
            {"key": "eco", "name": "生态约束（负向）", "default": 0.20},
        ],
    },
}

# 刚性约束：永久基本农田 / 生态保护红线 内 → 强制不适宜建设（联动 18）
RIGID_CONSTRAINT_ZONES = {"permanent_basic_farmland", "ecological_red_line"}


def suitability_evaluate(db, target: str, weights: dict, scope: dict,
                         project_id: int = None) -> dict:
    """格网法多因子加权叠加评价（三区三线刚性约束 + 结果持久化）。"""
    from shapely.geometry import mapping
    scope, _ = resolve_project_scope(db, project_id, scope)
    scope_g = _scope_geom(scope)
    if scope_g is None:
        raise ValueError("请提供评价范围")

    pois = _load_pois(db)
    zones = _load_zones(db)
    parcels = _load_parcels(db, None)
    traffic = [p["point"] for p in pois if p["poi_type"] == "交通"]
    services = [p["point"] for p in pois if p["poi_type"] in ("教育", "医疗", "休闲", "商业")]
    water = [p["point"] for p in pois if p["poi_type"] in ("休闲",)]  # 演示：以休闲设施近似水源
    builtup = [p["geom"].centroid for p in parcels if p["land_use"] in
               ("商服用地", "工矿仓储用地", "住宅用地", "公共管理与公共服务用地")]
    rigid = [(z, z["geom"]) for z in zones if z["zone_type"] in RIGID_CONSTRAINT_ZONES]

    def min_dist_m(point, geoms):
        if not geoms:
            return 1e9
        return min(point.distance(g) * 111320 * math.cos(math.radians(point.y))
                   for g in geoms)

    def score_dist(point, geoms, full_m=500.0, zero_m=3000.0):
        d = min_dist_m(point, geoms)
        if d <= full_m:
            return 100.0
        if d >= zero_m:
            return 20.0
        return round(20 + 80 * (zero_m - d) / (zero_m - full_m), 1)

    N = 40
    minx, miny, maxx, maxy = scope_g.bounds
    cell_w = (maxx - minx) / N
    cell_h = (maxy - miny) / N
    cells = []
    grid_records = []
    for i in range(N):
        for j in range(N):
            cx0, cy0 = minx + j * cell_w, miny + i * cell_h
            center = Point(cx0 + cell_w / 2, cy0 + cell_h / 2)
            if not scope_g.contains(center):
                continue
            geom = {
                "type": "Polygon",
                "coordinates": [[[cx0, cy0], [cx0 + cell_w, cy0],
                                 [cx0 + cell_w, cy0 + cell_h], [cx0, cy0 + cell_h], [cx0, cy0]]],
            }
            factor_scores = {
                "traffic": score_dist(center, traffic),
                "service": score_dist(center, services),
                "eco": 100.0,
                "builtup": score_dist(center, builtup, 300, 2000),
                "water": score_dist(center, water, 300, 2000),
                "flat": 60.0 + 40.0 * abs(math.sin(center.x * 60 + center.y * 40)),  # 模拟地形
            }
            # 刚性约束：格网中心落在永久基本农田/生态保护红线内 → 强制不适宜
            excluded = None
            for z, zg in rigid:
                if zg.contains(center):
                    excluded = z["zone_name"]
                    break
            if excluded:
                total = 0.0
                level = "不适宜"
                factor_scores["excluded"] = True
                factor_scores["exclude_reason"] = excluded
            else:
                total = sum(weights.get(k, 0) * factor_scores.get(k, 0) for k in weights)
                if total >= 80:
                    level = "高度适宜"
                elif total >= 60:
                    level = "中等适宜"
                elif total >= 40:
                    level = "勉强适宜"
                else:
                    level = "不适宜"
                factor_scores["excluded"] = False
            cells.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {"score": round(total, 1), "level": level,
                               **{k: v for k, v in factor_scores.items()}},
            })
            grid_records.append({"geometry": geom, "score": round(total, 1),
                                 "level": level, "factors_json": factor_scores})

    stats = {}
    for c in cells:
        lv = c["properties"]["level"]
        stats[lv] = stats.get(lv, 0) + 1

    # 持久化（按项目覆盖旧结果）
    if project_id:
        _clear_grids(db, project_id)
        _insert_grids(db, project_id, grid_records)

    return {
        "target": target,
        "weights": weights,
        "grid_size": N,
        "cells_geojson": {"type": "FeatureCollection", "features": cells},
        "stats": [{"level": k, "count": v} for k, v in
                  sorted(stats.items(), key=lambda kv: ["高度适宜", "中等适宜", "勉强适宜", "不适宜"].index(kv[0]))],
        "persisted": project_id is not None,
    }


def _insert_grids(db, project_id: int, records: list):
    if is_demo():
        pid0 = demo_data.next_id(demo_data.SUITABILITY_GRIDS)
        for i, rec in enumerate(records):
            demo_data.SUITABILITY_GRIDS.append({
                "id": pid0 + i, "project_id": project_id,
                "score": rec["score"], "level": rec["level"],
                "factors_json": rec["factors_json"], "geometry": rec["geometry"],
            })
        return
    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import SuitabilityGrid
    for rec in records:
        db.add(SuitabilityGrid(
            project_id=project_id, score=rec["score"], level=rec["level"],
            factors_json=rec["factors_json"],
            geom=ST_GeomFromGeoJSON(json.dumps(rec["geometry"])),
        ))
    db.commit()


# ===========================================================================
# 模块三：服务设施可达性分析（生活圈覆盖 + 结果持久化）
# ===========================================================================

def accessibility_analyze(db, facility_types: list, radius_m: float,
                          scope: Optional[dict] = None,
                          project_id: Optional[int] = None) -> dict:
    """地块到设施的可达性分析：覆盖判定 + 盲区清单（结果持久化）。"""
    scope, _ = resolve_project_scope(db, project_id, scope)
    scope_g = _scope_geom(scope)
    parcels = _load_parcels(db, None)
    pois = _load_pois(db)
    if scope_g:
        parcels = [p for p in parcels if p["geom"].intersects(scope_g)]
    type_set = set(facility_types)
    facilities = [p for p in pois if not type_set or p["poi_type"] in type_set]

    features = []
    gaps = []
    gap_ids = []
    covered_count = 0
    lon_scale = 111320.0 * math.cos(math.radians(settings.demo_center[1]))
    for p in parcels:
        center = p["geom"].centroid
        near = []
        for f in facilities:
            dist = f["point"].distance(center) * lon_scale
            if dist <= radius_m:
                near.append({"name": f["name"], "poi_type": f["poi_type"], "distance_m": round(dist, 0)})
        covered = len(near) > 0
        if covered:
            covered_count += 1
        else:
            gaps.append({"parcel_code": p["parcel_code"], "name": p["name"],
                         "land_use": p["land_use"], "parcel_id": p["id"],
                         "reason": f"{radius_m}m 内无所选设施"})
            gap_ids.append(p["id"])
        from shapely.geometry import mapping
        features.append({
            "type": "Feature",
            "geometry": mapping(p["geom"]),
            "properties": {
                "id": p["id"], "parcel_code": p["parcel_code"], "name": p["name"],
                "land_use": p["land_use"], "covered": covered,
                "facility_count": len(near),
                "facility_types": sorted({n["poi_type"] for n in near}),
                "nearby": near[:10],
            },
        })
    total = len(parcels)
    result = {
        "radius_m": radius_m,
        "facility_types": facility_types,
        "parcel_total": total,
        "covered_count": covered_count,
        "coverage_rate": round(covered_count / total, 4) if total else 0,
        "gap_count": len(gaps),
        "gap_parcel_ids": gap_ids,
        "gaps": gaps,
        "parcels_geojson": {"type": "FeatureCollection", "features": features},
    }

    # 持久化
    if project_id:
        _clear_accessibility(db, project_id)
        if is_demo():
            pid = demo_data.next_id(demo_data.ACCESSIBILITY_RESULTS)
            demo_data.ACCESSIBILITY_RESULTS.append({
                "id": pid, "project_id": project_id,
                "facility_types": facility_types, "radius_m": radius_m,
                "parcel_total": total, "covered_count": covered_count,
                "coverage_rate": result["coverage_rate"], "gap_parcel_ids": gap_ids,
            })
        else:
            from ..models import AccessibilityResult
            db.add(AccessibilityResult(
                project_id=project_id, facility_types=facility_types,
                radius_m=radius_m, parcel_total=total, covered_count=covered_count,
                coverage_rate=result["coverage_rate"], gap_parcel_ids=gap_ids,
            ))
            db.commit()
        result["persisted"] = True
    return result


# ===========================================================================
# 模块联动：可达性盲区 × 适宜性评价 → 建议新增设施选址（联动 19）
# ===========================================================================

def facility_sites(db, project_id: int) -> dict:
    """推荐设施选址：可达性盲区 ∩ 适宜性评价（高度/中等适宜）格网。"""
    access_rows = list_accessibility(db, project_id=project_id)
    if not access_rows:
        return {"features": [], "hint": "尚未执行可达性分析"}
    latest = access_rows[0]
    gap_ids = latest.get("gap_parcel_ids") or []

    grids_fc = list_grids(db, project_id=project_id)
    suitable = [
        shape(g["geometry"]) for g in grids_fc["features"]
        if g["properties"]["level"] in ("高度适宜", "中等适宜")
    ]
    if not suitable:
        return {"features": [], "hint": "尚未执行适宜性评价或范围内无适宜格网"}

    parcels_by_id = {p["id"]: p for p in _load_parcels(db, None)}
    from shapely.geometry import mapping
    features = []
    for pid in gap_ids:
        parcel = parcels_by_id.get(pid)
        if not parcel:
            continue
        pg = parcel["geom"]
        for sg in suitable:
            inter = pg.intersection(sg)
            if not inter.is_empty and inter.area > 0:
                features.append({
                    "type": "Feature", "geometry": mapping(inter),
                    "properties": {
                        "parcel_id": pid, "parcel_code": parcel["parcel_code"],
                        "parcel_name": parcel["name"], "land_use": parcel["land_use"],
                        "suggest": "建议新增公共服务设施（盲区 ∩ 适宜布局区）",
                    },
                })
    return {"type": "FeatureCollection", "features": features,
            "count": len(features),
            "gap_parcel_count": len(gap_ids)}

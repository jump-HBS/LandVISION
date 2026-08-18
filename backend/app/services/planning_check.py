# -*- coding: utf-8 -*-
"""
三区三线合规性体检服务（v2.0 规则矩阵版）。

核心：用地类型 × 管控区类型 → 结论（conflict/warning/pass）的规则矩阵判定。
  * 规则矩阵可配置（backend/app/data/planning_rules.json，services/planning_rules.py 读写）；
  * 每条结论附带"判定依据"（含重叠面积，亩），前端地块详情/台账可直接展示；
  * 批量体检结果持久化到 planning_check_results（按项目关联，可追溯、复用）；
  * 支持对转移矩阵变化图斑（land_change_patches）直接体检。

结论等级：冲突 > 警告 > 提示 > 通过。
"""
import json
from typing import Optional

from shapely.geometry import shape

from ..config import settings
from ..schemas import ZONE_TYPE_LABELS, ZONE_TYPES
from .. import demo_data
from .spatial import is_demo
from .planning_rules import verdict_for, verdict_level

LEVEL_ORDER = {"冲突": 3, "警告": 2, "提示": 1, "通过": 0}


def _mu(area_sqm: float) -> float:
    """平方米 → 亩（1 ㎡ = 0.0015 亩）。"""
    return round(area_sqm * 0.0015, 2)


def _reason(land_use: str, zone_label: str, conclusion: str, area_sqm: float) -> str:
    """判定依据文案。"""
    mu = _mu(area_sqm)
    if conclusion == "conflict":
        return f"「{land_use}」占用{zone_label} {mu} 亩，属禁止行为"
    if conclusion == "warning":
        return f"「{land_use}」占用{zone_label} {mu} 亩，需专项论证/注意管控要求"
    return f"「{land_use}」占用{zone_label} {mu} 亩，符合管控要求"


def _area_m2_approx(geom) -> float:
    """shapely 面积（度²）→ 平方米近似（等距圆柱，按几何中心纬度换算）。"""
    import math
    lon_scale = 111320.0 * math.cos(math.radians(geom.centroid.y))
    lat_scale = 110540.0
    return abs(geom.area) * lon_scale * lat_scale


def _overlap_verdict(land_use: str, zone: dict, overlap_area_sqm: float) -> dict:
    """单条重叠的规则判定：{conclusion, level, reason}。"""
    conclusion = verdict_for(land_use, zone["zone_type"])
    level = verdict_level(conclusion)
    return {
        "conclusion": conclusion,
        "level": level,
        "reason": _reason(land_use, ZONE_TYPE_LABELS.get(zone["zone_type"], zone["zone_type"]),
                          conclusion, overlap_area_sqm),
    }


def _overall_level(levels) -> str:
    if not levels:
        return "通过"
    return max(levels, key=lambda x: LEVEL_ORDER[x])


# ---------------------------------------------------------------------------
# 结果持久化（planning_check_results）
# ---------------------------------------------------------------------------

def _clear_project_results(db, project_id: int):
    if is_demo():
        demo_data.PLANNING_CHECK_RESULTS[:] = [
            r for r in demo_data.PLANNING_CHECK_RESULTS if r.get("project_id") != project_id
        ]
        return
    from ..models import PlanningCheckResult
    db.query(PlanningCheckResult).filter(PlanningCheckResult.project_id == project_id).delete()
    db.commit()


def _insert_results(db, project_id: int, records: list):
    if not records:
        return
    if is_demo():
        pid0 = demo_data.next_id(demo_data.PLANNING_CHECK_RESULTS)
        for i, rec in enumerate(records):
            demo_data.PLANNING_CHECK_RESULTS.append({
                "id": pid0 + i, "project_id": project_id,
                "parcel_id": rec.get("parcel_id"), "zone_id": rec.get("zone_id"),
                "overlap_area_sqm": rec["overlap_area_sqm"],
                "conclusion": rec["level"], "created_at": None,
            })
        return
    from ..models import PlanningCheckResult
    for rec in records:
        db.add(PlanningCheckResult(
            project_id=project_id,
            parcel_id=rec.get("parcel_id"),
            zone_id=rec.get("zone_id"),
            overlap_area_sqm=rec["overlap_area_sqm"],
            conclusion=rec["level"],
        ))
    db.commit()


def list_results(db=None, project_id: Optional[int] = None,
                 parcel_id: Optional[int] = None) -> list:
    """查询体检结果（持久化数据，支持按项目/地块过滤）。"""
    if is_demo():
        return [
            {"id": r["id"], "project_id": r.get("project_id"), "parcel_id": r.get("parcel_id"),
             "zone_id": r.get("zone_id"), "overlap_area_sqm": r.get("overlap_area_sqm"),
             "conclusion": r.get("conclusion")}
            for r in demo_data.PLANNING_CHECK_RESULTS
            if (project_id is None or r.get("project_id") == project_id)
            and (parcel_id is None or r.get("parcel_id") == parcel_id)
        ]
    from ..models import PlanningCheckResult
    q = db.query(PlanningCheckResult)
    if project_id:
        q = q.filter(PlanningCheckResult.project_id == project_id)
    if parcel_id:
        q = q.filter(PlanningCheckResult.parcel_id == parcel_id)
    return [
        {"id": r.id, "project_id": r.project_id, "parcel_id": r.parcel_id,
         "zone_id": r.zone_id, "overlap_area_sqm": float(r.overlap_area_sqm or 0),
         "conclusion": r.conclusion}
        for r in q.order_by(PlanningCheckResult.id).all()
    ]


# ---------------------------------------------------------------------------
# 审查要素（三区三线）管理
# ---------------------------------------------------------------------------

def _zone_out(z: dict) -> dict:
    return {"id": z["id"], "zone_name": z["zone_name"], "zone_type": z["zone_type"],
            "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], z["zone_type"]),
            "zone_level": z.get("zone_level"), "control_desc": z.get("control_desc"),
            "project_id": z.get("project_id"), "period": z.get("period"),
            "locked": z.get("locked", False)}


def list_zones(db=None) -> list[dict]:
    if is_demo():
        return [_zone_out(z) for z in demo_data.PLANNING_ZONES]
    from ..models import PlanningZone
    return [
        {"id": r.id, "zone_name": r.zone_name, "zone_type": r.zone_type,
         "zone_type_label": ZONE_TYPE_LABELS.get(r.zone_type, r.zone_type),
         "zone_level": r.zone_level, "control_desc": r.control_desc,
         "project_id": r.project_id, "period": r.period, "locked": r.locked}
        for r in db.query(PlanningZone).all()
    ]


def zones_geojson(db=None) -> dict:
    if is_demo():
        return demo_data.zones_geojson()
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping
    from ..models import PlanningZone
    features = [
        {"type": "Feature", "geometry": mapping(to_shape(r.geom)), "properties": {
            "id": r.id, "zone_name": r.zone_name, "zone_type": r.zone_type,
            "zone_type_label": ZONE_TYPE_LABELS.get(r.zone_type, r.zone_type),
            "zone_level": r.zone_level, "control_desc": r.control_desc,
            "project_id": r.project_id, "locked": r.locked}}
        for r in db.query(PlanningZone).all()
    ]
    return {"type": "FeatureCollection", "features": features}


def create_zone(data: dict, db=None) -> dict:
    """新增三区三线控制线（标准三线英文代码）。"""
    zone_type = data["zone_type"]
    if zone_type not in ZONE_TYPES:
        raise ValueError(f"管控区类型必须为：{'/'.join(ZONE_TYPES)}")
    zone_name = data.get("zone_name") or ZONE_TYPE_LABELS[zone_type]
    if is_demo():
        pid = demo_data.next_id(demo_data.PLANNING_ZONES)
        new = {
            "id": pid,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "zone_level": data.get("zone_level"),
            "control_desc": data.get("control_desc"),
            "project_id": data.get("project_id"),
            "period": data.get("period"),
            "locked": data.get("locked", False),
            "area_sqm": None,
            "geometry": data["geometry"],
        }
        demo_data.PLANNING_ZONES.append(new)
        return _zone_out(new)

    from geoalchemy2.functions import ST_GeomFromGeoJSON
    from ..models import PlanningZone
    row = PlanningZone(
        zone_name=zone_name,
        zone_type=zone_type,
        zone_level=data.get("zone_level"),
        control_desc=data.get("control_desc"),
        project_id=data.get("project_id"),
        period=data.get("period"),
        locked=data.get("locked", False),
        geom=ST_GeomFromGeoJSON(json.dumps(data["geometry"])),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "zone_name": row.zone_name, "zone_type": row.zone_type,
            "zone_type_label": ZONE_TYPE_LABELS[row.zone_type],
            "zone_level": row.zone_level, "control_desc": row.control_desc,
            "project_id": row.project_id, "period": row.period, "locked": row.locked}


def delete_zone(zone_id: int, db=None) -> bool:
    if is_demo():
        z = next((x for x in demo_data.PLANNING_ZONES if x["id"] == zone_id), None)
        if not z:
            return False
        if z.get("locked"):
            raise ValueError(f"控制线已锁定，解除锁定后才能删除：{z['zone_name']}")
        demo_data.PLANNING_ZONES.remove(z)
        return True
    from ..models import PlanningZone
    row = db.query(PlanningZone).filter(PlanningZone.id == zone_id).first()
    if not row:
        return False
    if row.locked:
        raise ValueError(f"控制线已锁定，解除锁定后才能删除：{row.zone_name}")
    db.delete(row)
    db.commit()
    return True


def import_zones_from_zip(zip_bytes: bytes, db=None, name_field: str = None,
                          type_field: str = None, zone_type: str = None,
                          project_id: Optional[int] = None,
                          period: Optional[str] = None) -> dict:
    """SHP 导入三区三线控制线（边界由用户导入，类型统一指定或按字段容错映射）。"""
    from .shp_import import _pick_field, parse_shp_zip

    parsed = parse_shp_zip(zip_bytes)
    fields = parsed["fields"]
    name_f = _pick_field(fields, ["name", "NAME", "XMMC", "MC", "zone_name"], name_field)
    type_f = _pick_field(fields, ["type", "TYPE", "zone_type", "LX", "类型"], type_field)

    def normalize(raw: str) -> str:
        text = (raw or "").strip()
        if text in ZONE_TYPES:
            return text
        if "红线" in text:
            return "ecological_red_line"
        if "农田" in text:
            return "permanent_basic_farmland"
        if "边界" in text:
            return "urban_growth_boundary"
        return ""

    fixed_type = (zone_type or "").strip() or None
    if fixed_type and fixed_type not in ZONE_TYPES:
        raise ValueError(f"类型必须为：{'/'.join(ZONE_TYPES)}")

    imported, skipped = 0, []
    for f in parsed["features"]:
        geom = f["geometry"]
        if geom["type"] not in ("Polygon", "MultiPolygon"):
            skipped.append({"reason": "仅支持面要素", "name": ""})
            continue
        polys = [{"type": "Polygon", "coordinates": rings}
                 for rings in geom["coordinates"]] if geom["type"] == "MultiPolygon" else [geom]
        props = f["properties"]
        feature_name = str(props.get(name_f) or "").strip() if name_f else ""
        ztype = fixed_type or (normalize(str(props.get(type_f) or "")) if type_f else "")
        if not ztype:
            skipped.append({"reason": "无法识别控制线类型（请指定导入类型）",
                            "name": feature_name})
            continue
        zname = feature_name or ZONE_TYPE_LABELS[ztype]
        for idx, poly in enumerate(polys):
            suffix = f"-{idx + 1}" if len(polys) > 1 else ""
            try:
                create_zone({
                    "zone_name": f"{zname}{suffix}",
                    "zone_type": ztype,
                    "zone_level": None,
                    "control_desc": f"SHP 导入（{ZONE_TYPE_LABELS[ztype]}）",
                    "project_id": project_id,
                    "period": period,
                    "geometry": poly,
                }, db)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                skipped.append({"reason": str(exc), "name": zname})
    return {"imported": imported, "skipped": skipped, "fields": fields}


# ---------------------------------------------------------------------------
# 单地块 / 任意几何 合规检查（规则矩阵判定）
# ---------------------------------------------------------------------------

def _check_with_geom(parcel_geom_geojson: dict, land_use: str, zones) -> dict:
    """对给定 GeoJSON 几何执行体检（Demo 模式与检查输入共用）。"""
    parcel_g = shape(parcel_geom_geojson)
    parcel_area = _area_m2_approx(parcel_g)
    results = []
    for z in zones:
        zone_g = shape(z["geometry"])
        if not zone_g.intersects(parcel_g):
            continue
        inter = zone_g.intersection(parcel_g)
        inter_area = _area_m2_approx(inter)
        ratio = inter_area / parcel_area if parcel_area > 0 else 0
        v = _overlap_verdict(land_use, z, inter_area)
        results.append({
            "zone_id": z["id"],
            "zone_name": z["zone_name"],
            "zone_type": z["zone_type"],
            "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], z["zone_type"]),
            "zone_level": z.get("zone_level"),
            "control_desc": z.get("control_desc"),
            "overlap_area_sqm": round(inter_area, 2),
            "overlap_mu": _mu(inter_area),
            "overlap_ratio": round(ratio, 4),
            "conclusion": v["conclusion"],
            "level": v["level"],
            "message": v["reason"],
        })
    overall = _overall_level([r["level"] for r in results])
    return {"overall": overall, "details": results}


def check_parcel(parcel_id: int, db=None) -> Optional[dict]:
    """对指定地块执行三区三线体检。"""
    if is_demo():
        parcel = next((p for p in demo_data.PARCELS if p["id"] == parcel_id), None)
        if not parcel:
            return None
        result = _check_with_geom(parcel["geometry"], parcel["land_use"],
                                  demo_data.PLANNING_ZONES)
        result["parcel"] = {k: parcel.get(k) for k in (
            "id", "parcel_code", "name", "land_use", "district", "area_sqm",
            "far_limit", "height_limit", "period", "project_id", "locked")}
        return result

    from geoalchemy2.functions import ST_Intersection, ST_Area, ST_Transform, ST_Intersects
    from ..models import Parcel, PlanningZone

    parcel_row = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel_row:
        return None
    parcel_area = float(parcel_row.area_sqm or 0)
    rows = (
        db.query(PlanningZone, ST_Area(ST_Transform(ST_Intersection(Parcel.geom, PlanningZone.geom), 3857)))
        .filter(Parcel.id == parcel_id, ST_Intersects(Parcel.geom, PlanningZone.geom))
        .all()
    )
    results = []
    for zone, inter_area in rows:
        overlap = float(inter_area or 0)
        v = _overlap_verdict(parcel_row.land_use,
                             {"zone_type": zone.zone_type}, overlap)
        results.append({
            "zone_id": zone.id, "zone_name": zone.zone_name, "zone_type": zone.zone_type,
            "zone_type_label": ZONE_TYPE_LABELS.get(zone.zone_type, zone.zone_type),
            "zone_level": zone.zone_level, "control_desc": zone.control_desc,
            "overlap_area_sqm": round(overlap, 2), "overlap_mu": _mu(overlap),
            "overlap_ratio": round(overlap / parcel_area, 4) if parcel_area > 0 else 0,
            "conclusion": v["conclusion"], "level": v["level"], "message": v["reason"],
        })
    overall = _overall_level([r["level"] for r in results])
    return {
        "overall": overall,
        "details": results,
        "parcel": {
            "id": parcel_row.id, "parcel_code": parcel_row.parcel_code,
            "name": parcel_row.name, "land_use": parcel_row.land_use,
            "district": parcel_row.district,
            "area_sqm": parcel_area,
            "far_limit": float(parcel_row.far_limit) if parcel_row.far_limit else None,
            "height_limit": float(parcel_row.height_limit) if parcel_row.height_limit else None,
            "period": parcel_row.period, "project_id": parcel_row.project_id,
            "locked": parcel_row.locked,
        },
    }


def check_geometry(geometry: dict, land_use: str = "其他土地", db=None) -> dict:
    """对任意 GeoJSON 几何做体检（不落库）。"""
    if is_demo():
        return _check_with_geom(geometry, land_use, demo_data.PLANNING_ZONES)

    from geoalchemy2.functions import (ST_GeomFromGeoJSON, ST_Intersects,
                                       ST_Intersection, ST_Area, ST_Transform)
    from ..models import PlanningZone

    input_geom = ST_GeomFromGeoJSON(json.dumps(geometry))
    area_sqm = db.scalar(ST_Area(ST_Transform(input_geom, 3857))) or 0
    rows = (
        db.query(PlanningZone, ST_Area(ST_Transform(ST_Intersection(input_geom, PlanningZone.geom), 3857)))
        .filter(ST_Intersects(input_geom, PlanningZone.geom))
        .all()
    )
    results = []
    for zone, inter_area in rows:
        overlap = float(inter_area or 0)
        v = _overlap_verdict(land_use, {"zone_type": zone.zone_type}, overlap)
        results.append({
            "zone_id": zone.id, "zone_name": zone.zone_name, "zone_type": zone.zone_type,
            "zone_type_label": ZONE_TYPE_LABELS.get(zone.zone_type, zone.zone_type),
            "zone_level": zone.zone_level, "control_desc": zone.control_desc,
            "overlap_area_sqm": round(overlap, 2), "overlap_mu": _mu(overlap),
            "overlap_ratio": round(overlap / area_sqm, 4) if area_sqm > 0 else 0,
            "conclusion": v["conclusion"], "level": v["level"], "message": v["reason"],
        })
    overall = _overall_level([r["level"] for r in results])
    return {"overall": overall, "details": results}


# ---------------------------------------------------------------------------
# 批量体检：审查范围内，地块 × 控制线 的占用矩阵（持久化）
# ---------------------------------------------------------------------------

def review_occupancy(db=None, scope: Optional[dict] = None,
                     zone_ids: Optional[list] = None,
                     parcel_ids: Optional[list] = None,
                     project_id: Optional[int] = None) -> dict:
    """计算所选地块占用各类型控制线的面积（规则矩阵判定 + 结果持久化）。"""
    if is_demo():
        parcels = list(demo_data.PARCELS)
        zones = list(demo_data.PLANNING_ZONES)
        if scope:
            scope_g = shape(scope)
            parcels = [p for p in parcels if _geom_in_scope(p["geometry"], scope_g)]
            zones = [z for z in zones if _geom_in_scope(z["geometry"], scope_g)]
        if zone_ids:
            idset = set(zone_ids)
            zones = [z for z in zones if z["id"] in idset]
        if parcel_ids:
            pidset = set(parcel_ids)
            parcels = [p for p in parcels if p["id"] in pidset]
        parcels = [{"id": p["id"], "parcel_code": p["parcel_code"], "name": p["name"],
                    "land_use": p["land_use"], "area_sqm": p.get("area_sqm"),
                    "geom": p["geometry"]} for p in parcels]
        zones = [{"id": z["id"], "zone_name": z["zone_name"], "zone_type": z["zone_type"],
                  "zone_level": z.get("zone_level"), "geom": z["geometry"]} for z in zones]
    else:
        from geoalchemy2.functions import ST_Intersection, ST_Area, ST_Transform
        from ..models import Parcel, PlanningZone
        parcel_query = db.query(Parcel)
        zone_query = db.query(PlanningZone)
        if zone_ids:
            zone_query = zone_query.filter(PlanningZone.id.in_(zone_ids))
        if parcel_ids:
            parcel_query = parcel_query.filter(Parcel.id.in_(parcel_ids))
        parcels_rows = parcel_query.all()
        zones_rows = zone_query.all()
        if scope:
            scope_g = shape(scope)
            parcels_rows = [p for p in parcels_rows
                            if _geom_in_scope(_to_geojson(p.geom), scope_g)]
            zones_rows = [z for z in zones_rows
                          if _geom_in_scope(_to_geojson(z.geom), scope_g)]
        parcels = [{"id": p.id, "parcel_code": p.parcel_code, "name": p.name,
                    "land_use": p.land_use, "area_sqm": float(p.area_sqm or 0),
                    "geom": _to_geojson(p.geom)} for p in parcels_rows]
        zones = [{"id": z.id, "zone_name": z.zone_name, "zone_type": z.zone_type,
                  "zone_level": z.zone_level, "geom": _to_geojson(z.geom)}
                 for z in zones_rows]

    rows = []
    totals = {}
    persist_records = []
    for p in parcels:
        pg = shape(p["geom"])
        overlaps = []
        for z in zones:
            zg = shape(z["geom"])
            if not zg.intersects(pg):
                continue
            inter = zg.intersection(pg)
            area = _area_m2_approx(inter)
            if area <= 0.01:
                continue
            v = _overlap_verdict(p["land_use"], z, area)
            overlaps.append({
                "zone_id": z["id"], "zone_name": z["zone_name"],
                "zone_type": z["zone_type"],
                "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], z["zone_type"]),
                "overlap_area_sqm": round(area, 2),
                "overlap_mu": _mu(area),
                "conclusion": v["conclusion"], "level": v["level"],
                "message": v["reason"],
            })
            totals.setdefault(z["zone_type"],
                              {"zone_type": z["zone_type"],
                               "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], z["zone_type"]),
                               "total_area_sqm": 0.0, "conflict_count": 0, "warning_count": 0})
            totals[z["zone_type"]]["total_area_sqm"] += area
            if v["conclusion"] == "conflict":
                totals[z["zone_type"]]["conflict_count"] += 1
            elif v["conclusion"] == "warning":
                totals[z["zone_type"]]["warning_count"] += 1
            persist_records.append({
                "parcel_id": p["id"], "zone_id": z["id"],
                "overlap_area_sqm": round(area, 2),
                "level": v["level"],
            })
        rows.append({
            "parcel_id": p["id"], "parcel_code": p["parcel_code"],
            "name": p["name"], "land_use": p["land_use"],
            "area_sqm": p.get("area_sqm"),
            "overlaps": overlaps,
            "overall": _overall_level([o["level"] for o in overlaps]),
            "total_occupied_sqm": round(sum(o["overlap_area_sqm"] for o in overlaps), 2),
        })

    # 持久化（按项目覆盖旧结果）
    if project_id:
        _clear_project_results(db, project_id)
        _insert_results(db, project_id, persist_records)

    totals_list = [
        {**v, "total_area_sqm": round(v["total_area_sqm"], 2)}
        for v in sorted(totals.values(), key=lambda x: x["zone_type"])
    ]
    return {
        "scope_area_sqm": round(_area_m2_approx(shape(scope)), 2) if scope else None,
        "parcel_count": len(parcels),
        "zone_count": len(zones),
        "rows": rows,
        "totals": totals_list,
        "persisted": project_id is not None,
    }


def review_patches(db=None, project_id: int = None,
                   patch_ids: Optional[list] = None) -> dict:
    """对转移矩阵变化图斑做三区三线合规检查（联动：模块一 → 模块四）。"""
    if is_demo():
        patches = [p for p in demo_data.LAND_CHANGE_PATCHES
                   if p.get("project_id") == project_id]
        if patch_ids:
            idset = set(patch_ids)
            patches = [p for p in patches if p["id"] in idset]
        zones = list(demo_data.PLANNING_ZONES)
        zone_geoms = [(z, shape(z["geometry"])) for z in zones]
    else:
        from ..models import LandChangePatch, PlanningZone
        from geoalchemy2.shape import to_shape
        from shapely.geometry import mapping
        q = db.query(LandChangePatch).filter(LandChangePatch.project_id == project_id)
        if patch_ids:
            q = q.filter(LandChangePatch.id.in_(patch_ids))
        patch_rows = q.all()
        zone_rows = db.query(PlanningZone).all()
        patches = [{"id": p.id, "from_land_use": p.from_land_use, "to_land_use": p.to_land_use,
                    "change_type": p.change_type, "area_sqm": float(p.area_sqm or 0),
                    "geom": mapping(to_shape(p.geom))} for p in patch_rows]
        zones = [{"id": z.id, "zone_name": z.zone_name, "zone_type": z.zone_type,
                  "geom": mapping(to_shape(z.geom))} for z in zone_rows]
        zone_geoms = [(z, shape(z["geom"])) for z in zones]

    rows = []
    persist_records = []
    conflict_patch_ids = []
    for p in patches:
        pg = shape(p["geom"])
        land_use = p["to_land_use"] or p["from_land_use"] or "其他土地"
        overlaps = []
        for z, zg in zone_geoms:
            if not zg.intersects(pg):
                continue
            inter = zg.intersection(pg)
            area = _area_m2_approx(inter)
            if area <= 0.01:
                continue
            v = _overlap_verdict(land_use, z, area)
            overlaps.append({
                "zone_id": z["id"], "zone_name": z["zone_name"],
                "zone_type": z["zone_type"],
                "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], z["zone_type"]),
                "overlap_area_sqm": round(area, 2), "overlap_mu": _mu(area),
                "conclusion": v["conclusion"], "level": v["level"], "message": v["reason"],
            })
            persist_records.append({
                "parcel_id": None, "zone_id": z["id"],
                "overlap_area_sqm": round(area, 2), "level": v["level"],
            })
        overall = _overall_level([o["level"] for o in overlaps])
        if overall == "冲突":
            conflict_patch_ids.append(p["id"])
        rows.append({
            "patch_id": p["id"], "change_type": p["change_type"],
            "from_land_use": p["from_land_use"], "to_land_use": p["to_land_use"],
            "land_use": land_use,
            "area_sqm": p.get("area_sqm"),
            "overlaps": overlaps, "overall": overall,
        })

    _clear_project_results(db, project_id)
    _insert_results(db, project_id, persist_records)

    # 图斑冲突标记回写
    if is_demo():
        for p in demo_data.LAND_CHANGE_PATCHES:
            if p.get("project_id") == project_id:
                p["is_conflict"] = p["id"] in conflict_patch_ids
    else:
        from ..models import LandChangePatch
        for p in db.query(LandChangePatch).filter(LandChangePatch.project_id == project_id).all():
            p.is_conflict = p.id in conflict_patch_ids
        db.commit()

    return {
        "patch_count": len(patches),
        "conflict_count": len(conflict_patch_ids),
        "conflict_patch_ids": conflict_patch_ids,
        "rows": rows,
        "persisted": True,
    }


# ---------------------------------------------------------------------------
# 问题台账 CSV
# ---------------------------------------------------------------------------

def review_to_csv(review: dict) -> str:
    """把批量体检结果组装为问题台账 CSV（三区三线体检输出）。"""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["地块编号", "地块名称", "用地类型", "涉及管控区类型",
                     "重叠面积(公顷)", "结论", "判定依据"])

    rows = sorted(review.get("rows", []), key=lambda r: -r["total_occupied_sqm"])
    conflict_count = 0
    for r in rows:
        for o in r.get("overlaps", []):
            if o["level"] == "冲突":
                conflict_count += 1
            writer.writerow([
                r["parcel_code"], r["name"], r["land_use"],
                o["zone_type_label"],
                f"{o['overlap_area_sqm'] / 10000:.4f}",
                o["level"],
                o["message"],
            ])
    writer.writerow([])
    writer.writerow(["冲突重叠记录合计", conflict_count, "", "", "", "", ""])
    return "\ufeff" + buf.getvalue()  # BOM 保证 Excel 打开中文不乱码


def _to_geojson(wkb) -> dict:
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping
    return mapping(to_shape(wkb))


def _geom_in_scope(geom_geojson: dict, scope_geom) -> bool:
    """地块/控制线是否与审查范围相交。"""
    return shape(geom_geojson).intersects(scope_geom)

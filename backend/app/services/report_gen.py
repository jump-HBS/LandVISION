# -*- coding: utf-8 -*-
"""
报告 / 驾驶舱统筹数据服务（v2.0：项目感知 + 持久化结果优先 + 综合分析）。

collect_dashboard(db, project_id, scope, scope_label)：
  1. 优先从持久化结果表读取各模块数据（land_change_patches / suitability_grids /
     planning_check_results / accessibility_results），无持久化结果时实时计算兜底；
  2. 组装项目概况、流程进度（各模块完成状态）、问题清单与对策建议；
  3. 驾驶舱与报告共用该数据源，保证模块间一致。

generate_report / to_markdown 输出综合分析报告：
  一、项目概况 → 二、现状评价 → 三、问题识别 → 四、原因分析 → 五、规划建议 → 六、附录数据表。
"""
import json
from datetime import datetime
from typing import Optional

from shapely.geometry import shape

from ..config import settings
from ..schemas import LAND_USE_TYPES, ZONE_TYPE_LABELS
from .. import demo_data
from .spatial import is_demo
from .planning_check import review_occupancy, list_results as list_check_results
from .analysis import (transition_matrix, accessibility_analyze,
                       list_patches, list_grids, list_accessibility)
from .projects import get_project


def _scope_geom(scope: Optional[dict]):
    return shape(scope) if scope else None


def _in_scope_demo(geom_dict: dict, scope_g) -> bool:
    return scope_g is None or shape(geom_dict).intersects(scope_g)


def _land_use_stats(db=None, scope: Optional[dict] = None) -> list[dict]:
    scope_g = _scope_geom(scope)
    if is_demo():
        src = [p for p in demo_data.PARCELS if _in_scope_demo(p["geometry"], scope_g)]
        agg: dict[str, dict] = {}
        for p in src:
            entry = agg.setdefault(p["land_use"], {"count": 0, "area_sqm": 0.0})
            entry["count"] += 1
            entry["area_sqm"] += p["area_sqm"] or 0
        return [
            {"land_use": t, "count": agg.get(t, {}).get("count", 0),
             "area_sqm": round(agg.get(t, {}).get("area_sqm", 0), 2)}
            for t in LAND_USE_TYPES
        ]
    from sqlalchemy import func
    from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_Intersects
    from ..models import Parcel
    query = db.query(Parcel.land_use, func.count(Parcel.id), func.sum(Parcel.area_sqm))
    if scope:
        query = query.filter(ST_Intersects(Parcel.geom, ST_GeomFromGeoJSON(json.dumps(scope))))
    rows = query.group_by(Parcel.land_use).all()
    agg = {r[0]: {"count": r[1], "area_sqm": round(float(r[2] or 0), 2)} for r in rows}
    return [
        {"land_use": t, "count": agg.get(t, {}).get("count", 0),
         "area_sqm": agg.get(t, {}).get("area_sqm", 0)}
        for t in LAND_USE_TYPES
    ]


def _district_stats(db=None, scope: Optional[dict] = None) -> list[dict]:
    scope_g = _scope_geom(scope)
    if is_demo():
        agg: dict[str, dict] = {}
        for p in demo_data.PARCELS:
            if not _in_scope_demo(p["geometry"], scope_g):
                continue
            d = p.get("district") or p.get("region_code") or "未分区"
            entry = agg.setdefault(d, {"count": 0, "area_sqm": 0.0})
            entry["count"] += 1
            entry["area_sqm"] += p["area_sqm"] or 0
        return [
            {"district": k, "count": v["count"], "area_sqm": round(v["area_sqm"], 2)}
            for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["count"])
        ]
    from sqlalchemy import func
    from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_Intersects
    from ..models import Parcel
    query = db.query(Parcel.district, func.count(Parcel.id), func.sum(Parcel.area_sqm))
    if scope:
        query = query.filter(ST_Intersects(Parcel.geom, ST_GeomFromGeoJSON(json.dumps(scope))))
    rows = query.group_by(Parcel.district).all()
    return [
        {"district": r[0] or "未分区", "count": r[1], "area_sqm": round(float(r[2] or 0), 2)}
        for r in rows
    ]


def _transition_change_area(rows: list) -> float:
    total = 0.0
    for r in rows:
        f, t = r["from_use"], r["to_use"]
        if f == "（消失）" or t == "（新增）":
            total += r["area_sqm"]
        elif f != t:
            total += r["area_sqm"]
    return round(total, 2)


# ---------------------------------------------------------------------------
# 持久化结果聚合
# ---------------------------------------------------------------------------

def _transition_from_patches(db, project_id: int, scope) -> dict:
    """从 land_change_patches 聚合转移矩阵概览（持久化结果优先）。"""
    from collections import defaultdict
    fc = list_patches(db, project_id=project_id)
    feats = fc["features"]
    if not feats:
        return None
    agg = defaultdict(float)
    for f in feats:
        p = f["properties"]
        key = (p.get("from_land_use") or "—", p.get("to_land_use") or "—")
        agg[key] += float(p.get("area_sqm") or 0)
    rows = [{"from_use": k[0], "to_use": k[1], "area_sqm": round(v, 2)}
            for k, v in sorted(agg.items())]
    base = _count_parcels(db, "base", scope)
    current = _count_parcels(db, "current", scope)
    return {
        "has_data": True,
        "from_persisted": True,
        "base_count": base,
        "current_count": current,
        "change_count": fc["count"],
        "conflict_patch_count": sum(1 for f in feats if f["properties"].get("is_conflict")),
        "change_area_sqm": _transition_change_area(rows),
        "rows": rows,
        "summary": [],
    }


def _count_parcels(db, period: str, scope) -> int:
    scope_g = _scope_geom(scope)
    if is_demo():
        return sum(1 for p in demo_data.PARCELS
                   if p.get("period") == period and _in_scope_demo(p["geometry"], scope_g))
    from sqlalchemy import func
    from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_Intersects
    from ..models import Parcel
    q = db.query(func.count(Parcel.id)).filter(Parcel.period == period)
    if scope:
        q = q.filter(ST_Intersects(Parcel.geom, ST_GeomFromGeoJSON(json.dumps(scope))))
    return q.scalar() or 0


def _suitability_from_grids(db, project_id: int) -> Optional[dict]:
    fc = list_grids(db, project_id=project_id)
    feats = fc["features"]
    if not feats:
        return None
    stats = {}
    for f in feats:
        lv = f["properties"]["level"]
        stats[lv] = stats.get(lv, 0) + 1
    order = ["高度适宜", "中等适宜", "勉强适宜", "不适宜"]
    return {
        "from_persisted": True,
        "cell_total": fc["count"],
        "stats": [{"level": k, "count": v} for k, v in
                  sorted(stats.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99)],
    }


def _accessibility_from_results(db, project_id: int) -> Optional[dict]:
    rows = list_accessibility(db, project_id=project_id)
    if not rows:
        return None
    r = rows[0]
    gaps = []
    parcels = _load_parcels_dict(db)
    for pid in r.get("gap_parcel_ids") or []:
        p = parcels.get(pid)
        if p:
            gaps.append({"parcel_id": pid, "parcel_code": p["parcel_code"],
                         "name": p["name"], "land_use": p["land_use"],
                         "reason": f"{r['radius_m']}m 内无所选设施"})
    return {
        "from_persisted": True,
        "radius_m": r["radius_m"],
        "facility_types": r.get("facility_types") or [],
        "parcel_total": r["parcel_total"],
        "covered_count": r["covered_count"],
        "coverage_rate": r["coverage_rate"],
        "gap_count": len(gaps),
        "gap_parcel_ids": r.get("gap_parcel_ids") or [],
        "gaps": gaps,
    }


def _planning_from_results(db, project_id: int, scope) -> Optional[dict]:
    results = list_check_results(db, project_id=project_id)
    if not results:
        return None
    parcels = _load_parcels_dict(db)
    zones = _load_zones_dict(db)
    by_level = {"通过": 0, "提示": 0, "警告": 0, "冲突": 0}
    totals = {}
    rows_map = {}
    for r in results:
        by_level[r["conclusion"]] = by_level.get(r["conclusion"], 0) + 1
        z = zones.get(r["zone_id"])
        if z:
            t = totals.setdefault(z["zone_type"], {
                "zone_type": z["zone_type"],
                "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], z["zone_type"]),
                "total_area_sqm": 0.0})
            t["total_area_sqm"] += r["overlap_area_sqm"]
        p = parcels.get(r["parcel_id"])
        if p:
            row = rows_map.setdefault(r["parcel_id"], {
                "parcel_id": p["id"], "parcel_code": p["parcel_code"], "name": p["name"],
                "land_use": p["land_use"], "overlaps": [], "total_occupied_sqm": 0.0,
                "overall": "通过"})
            row["overlaps"].append({
                "zone_id": r["zone_id"], "zone_type": z["zone_type"] if z else "",
                "zone_type_label": ZONE_TYPE_LABELS.get(z["zone_type"], "") if z else "",
                "zone_name": z["zone_name"] if z else "",
                "overlap_area_sqm": r["overlap_area_sqm"], "level": r["conclusion"]})
            row["total_occupied_sqm"] += r["overlap_area_sqm"]
            if r["conclusion"] == "冲突" or (r["conclusion"] == "警告" and row["overall"] != "冲突"):
                row["overall"] = r["conclusion"]
    return {
        "from_persisted": True,
        "by_level": by_level,
        "conflict_count": by_level.get("冲突", 0),
        "review_rows": list(rows_map.values()),
        "review_totals": [{**v, "total_area_sqm": round(v["total_area_sqm"], 2)}
                          for v in totals.values()],
        "review_zone_count": len(zones),
        "review_parcel_count": len(rows_map),
    }


def _load_parcels_dict(db) -> dict:
    if is_demo():
        return {p["id"]: p for p in demo_data.PARCELS}
    from ..models import Parcel
    return {r.id: {"id": r.id, "parcel_code": r.parcel_code, "name": r.name,
                   "land_use": r.land_use} for r in db.query(Parcel).all()}


def _load_zones_dict(db) -> dict:
    if is_demo():
        return {z["id"]: z for z in demo_data.PLANNING_ZONES}
    from ..models import PlanningZone
    return {r.id: {"id": r.id, "zone_name": r.zone_name, "zone_type": r.zone_type}
            for r in db.query(PlanningZone).all()}


# ---------------------------------------------------------------------------
# 统筹汇总（驾驶舱 + 报告共用）
# ---------------------------------------------------------------------------

def collect_dashboard(db=None, project_id: Optional[int] = None,
                      scope: Optional[dict] = None,
                      scope_label: Optional[str] = None) -> dict:
    """按分析项目与范围聚合全模块数据（持久化结果优先，实时计算兜底）。"""
    project = get_project(project_id, db) if project_id else None
    if project and project.get("scope_geojson") and scope is None:
        scope = project["scope_geojson"]
    if scope_label is None:
        scope_label = project["name"] if project else "全量数据"
    scope_g = _scope_geom(scope)

    if is_demo():
        parcels = [p for p in demo_data.PARCELS if _in_scope_demo(p["geometry"], scope_g)]
        pois = [p for p in demo_data.POIS
                if scope_g is None or shape(p["geometry"]).intersects(scope_g)]
        zones = [z for z in demo_data.PLANNING_ZONES
                 if _in_scope_demo(z["geometry"], scope_g)]
        parcel_total = len(parcels)
        area_total = sum(p["area_sqm"] or 0 for p in parcels)
        poi_total = len(pois)
        zone_total = len(zones)
        region_total = len(demo_data.REGIONS)
    else:
        from sqlalchemy import func
        from geoalchemy2.functions import ST_GeomFromGeoJSON, ST_Intersects
        from ..models import Parcel, Poi, PlanningZone, Region

        def scoped(query, model):
            if not scope:
                return query
            return query.filter(ST_Intersects(model.geom, ST_GeomFromGeoJSON(json.dumps(scope))))

        parcel_total, area_total = scoped(
            db.query(func.count(Parcel.id), func.coalesce(func.sum(Parcel.area_sqm), 0)), Parcel
        ).one()
        poi_total = scoped(db.query(func.count(Poi.id)), Poi).scalar() or 0
        zone_total = scoped(db.query(func.count(PlanningZone.id)), PlanningZone).scalar() or 0
        region_total = db.query(func.count(Region.id)).scalar() or 0

    land_use = _land_use_stats(db, scope)
    districts = _district_stats(db, scope)

    # 各模块：持久化结果优先
    transition = _transition_from_patches(db, project_id, scope) if project_id else None
    if not transition:
        t = transition_matrix(db, scope=scope, project_id=project_id)
        transition = {
            "has_data": bool(t["base_count"] and t["current_count"]),
            "from_persisted": False,
            "hint": t.get("hint"),
            "base_count": t["base_count"],
            "current_count": t["current_count"],
            "change_count": len(t["changes_geojson"]["features"]),
            "conflict_patch_count": 0,
            "change_area_sqm": _transition_change_area(t["rows"]),
            "rows": t["rows"],
            "summary": t["summary"],
        }

    suitability = _suitability_from_grids(db, project_id) if project_id else None
    if suitability is None:
        suitability = {"from_persisted": False, "cell_total": 0, "stats": [],
                       "hint": "尚未执行适宜性评价（模块二）"}

    accessibility = _accessibility_from_results(db, project_id) if project_id else None
    if accessibility is None:
        a = accessibility_analyze(db, facility_types=[], radius_m=800, scope=scope)
        accessibility = {
            "from_persisted": False,
            "radius_m": a["radius_m"], "facility_types": [],
            "parcel_total": a["parcel_total"], "covered_count": a["covered_count"],
            "coverage_rate": a["coverage_rate"], "gap_count": a["gap_count"],
            "gap_parcel_ids": a.get("gap_parcel_ids", []), "gaps": a["gaps"],
        }

    planning = _planning_from_results(db, project_id, scope) if project_id else None
    if planning is None:
        r = review_occupancy(db, scope=scope, project_id=project_id)
        planning = {
            "from_persisted": False,
            "by_level": {}, "conflict_count": 0,
            "review_rows": r["rows"], "review_totals": r["totals"],
            "review_zone_count": r["zone_count"], "review_parcel_count": r["parcel_count"],
        }
        by = {"通过": 0, "提示": 0, "警告": 0, "冲突": 0}
        for row in r["rows"]:
            by[row["overall"]] = by.get(row["overall"], 0) + 1
        planning["by_level"] = by
        planning["conflict_count"] = by["冲突"]

    progress = {
        "transition": bool(transition["has_data"]),
        "suitability": bool(suitability.get("cell_total")),
        "planning": bool(planning.get("review_rows")),
        "accessibility": bool(project_id and accessibility.get("from_persisted")),
    }
    progress["missing"] = [k for k, v in progress.items() if not v]

    # ---------- 问题清单 ----------
    problems = []
    for row in planning["review_rows"]:
        for o in row.get("overlaps", []):
            if o["level"] in ("冲突", "警告"):
                problems.append({
                    "type": "三区三线" + ("冲突" if o["level"] == "冲突" else "警告"),
                    "title": f"地块 {row['name']}（{row['parcel_code']}）占用{o.get('zone_type_label', '')}",
                    "detail": f"「{row['land_use']}」重叠 {o['overlap_area_sqm'] / 10000:.2f} 公顷（{o['overlap_area_sqm'] * 0.0015:.2f} 亩）",
                    "severity": "high" if o["level"] == "冲突" else "medium",
                })
    for g in accessibility["gaps"]:
        problems.append({
            "type": "设施盲区",
            "title": f"地块 {g['name']}（{g['parcel_code']}）在 {accessibility['radius_m']}m 生活圈外",
            "detail": g.get("reason", "服务半径内无所选设施"),
            "severity": "medium",
        })
    if transition.get("conflict_patch_count"):
        problems.append({
            "type": "违规变化",
            "title": f"{transition['conflict_patch_count']} 个变化图斑与三区三线冲突",
            "detail": "在转移矩阵页点击「对变化图斑进行合规检查」查看明细",
            "severity": "high",
        })
    for k in progress["missing"]:
        problems.append({
            "type": "流程缺失",
            "title": f"尚未执行「{k}」分析",
            "detail": "按推荐流程补全分析后，本报告将自动纳入对应结论",
            "severity": "low",
        })
    problem_total = len(problems)
    problems = problems[:60]  # 大数据量下限制问题清单长度（总数单独返回）

    # ---------- 规划建议 ----------
    suggestions = []
    conflict_rows = [r for r in planning["review_rows"]
                     if any(o["level"] == "冲突" for o in r.get("overlaps", []))]
    if conflict_rows:
        names = "、".join(r["name"] for r in conflict_rows[:5])
        suggestions.append({
            "title": "冲突协调建议",
            "detail": f"{len(conflict_rows)} 宗地块与永久基本农田/生态保护红线冲突（{names}…），"
                      "建议调整用途、核减建设边界或开展专题论证后重新体检。"})
    if accessibility["gaps"]:
        suggestions.append({
            "title": "设施优化建议",
            "detail": f"{accessibility['gap_count']} 宗地块处于 {accessibility['radius_m']}m 生活圈盲区，"
                      "建议在盲区与适宜布局区交集处新增公共服务设施（可达性页「推荐设施选址」）。"})
    farmland_delta = 0.0
    for s in transition.get("summary", []):
        if s["land_use"] == "耕地":
            farmland_delta = s["delta_sqm"]
    if farmland_delta < 0:
        suggestions.append({
            "title": "耕地保护建议",
            "detail": f"耕地净减少 {abs(farmland_delta) / 10000:.2f} 公顷，建议落实占补平衡与进出平衡。"})
    if transition["change_count"] and not transition.get("conflict_patch_count"):
        suggestions.append({
            "title": "变化诊断建议",
            "detail": "建议对新增建设用地开展适宜性评价，校验选址是否落在高度/中等适宜区。"})
    if progress["missing"]:
        suggestions.append({
            "title": "流程补全建议",
            "detail": "建议按 地块管理 → 转移矩阵 → 三区三线体检 → 适宜性评价 → 可达性分析 顺序补全分析。"})

    return {
        "scope": {"label": scope_label, "has_scope": bool(scope)},
        "project": {
            "id": project["id"] if project else None,
            "name": project["name"] if project else None,
            "base_year": project["base_year"] if project else None,
            "current_year": project["current_year"] if project else None,
        },
        "progress": progress,
        "overview": {
            "parcel_total": parcel_total,
            "area_total_sqm": round(float(area_total), 2),
            "poi_total": poi_total,
            "planning_zone_total": zone_total,
            "region_total": region_total,
            "coverage_rate": accessibility["coverage_rate"],
        },
        "land_use_distribution": land_use,
        "district_distribution": districts,
        "transition_analysis": transition,
        "suitability": suitability,
        "planning_review": planning,
        "accessibility": accessibility,
        "problems": problems,
        "problem_total": problem_total,
        "suggestions": suggestions,
    }


def generate_report(db=None, project_name: str = "武汉市洪山区国土空间数据管理报告",
                    period: str = "2026 年第三季度", author: str = "LandVISION 系统",
                    project_id: Optional[int] = None,
                    scope: Optional[dict] = None,
                    scope_label: Optional[str] = None) -> dict:
    """生成综合分析报告：统筹数据（驾驶舱同源）+ 报告元信息。"""
    data = collect_dashboard(db, project_id=project_id, scope=scope, scope_label=scope_label)
    return {
        "meta": {
            "project_name": project_name,
            "period": period,
            "author": author,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "DEMO（内存数据）" if is_demo() else "POSTGIS（PostgreSQL + PostGIS）",
        },
        **data,
    }


def to_markdown(report: dict) -> str:
    """把综合分析报告渲染为 Markdown 文本（下载用）。"""
    m = report["meta"]
    o = report["overview"]
    s = report.get("scope", {})
    pr = report.get("project", {})
    pg = report.get("progress", {})
    p = report["planning_review"]
    t = report["transition_analysis"]
    a = report["accessibility"]
    su = report["suitability"]
    lines = [
        f"# {m['project_name']}",
        "",
        f"- **报告期**：{m['period']}",
        f"- **生成时间**：{m['generated_at']}",
        f"- **生成人**：{m['author']}",
        f"- **数据模式**：{m['mode']}",
        f"- **分析范围**：{s.get('label', '全量数据')}",
        "",
        "## 一、项目概况",
        "",
    ]
    if pr.get("name"):
        lines += [f"- 分析项目：{pr['name']}（基期 {pr.get('base_year')} 年 → 末期 {pr.get('current_year')} 年）"]
    lines += [
        f"- 地块总数：{o['parcel_total']} 宗，总面积 {o['area_total_sqm'] / 10000:.2f} 公顷",
        f"- 兴趣点 {o['poi_total']} 个，三区三线控制线 {o['planning_zone_total']} 条",
        f"- 设施可达性覆盖率（{a['radius_m']}m 生活圈）：{a['coverage_rate'] * 100:.1f}%",
        f"- 流程进度：转移矩阵 {'✓' if pg.get('transition') else '✗'} / 体检 {'✓' if pg.get('planning') else '✗'} / 适宜性 {'✓' if pg.get('suitability') else '✗'} / 可达性 {'✓' if pg.get('accessibility') else '✗'}",
        "",
        "## 二、现状评价",
        "",
        "### 2.1 用地结构（GB/T 21010-2017 一级类）",
        "",
        "| 用地类型 | 数量 | 面积(公顷) |",
        "|---|---:|---:|",
    ]
    for item in report["land_use_distribution"]:
        if item["count"] or item["area_sqm"]:
            lines.append(f"| {item['land_use']} | {item['count']} | {item['area_sqm'] / 10000:.2f} |")
    lines += ["", "### 2.2 行政区分布", "", "| 行政区 | 地块数 | 面积(公顷) |", "|---|---:|---:|"]
    for item in report["district_distribution"]:
        lines.append(f"| {item['district']} | {item['count']} | {item['area_sqm'] / 10000:.2f} |")
    lines += ["", "### 2.3 用地变化转移矩阵（模块一）", ""]
    if t["has_data"]:
        lines += [
            f"- 基期地块 {t['base_count']} 宗，末期地块 {t['current_count']} 宗；"
            f"变化图斑 {t['change_count']} 个，变化总面积 {t['change_area_sqm'] / 10000:.2f} 公顷",
            "",
            "| 基期地类 | 末期地类 | 转换面积(公顷) |",
            "|---|---|---:|",
        ]
        for r in t["rows"]:
            lines.append(f"| {r['from_use']} | {r['to_use']} | {r['area_sqm'] / 10000:.2f} |")
    else:
        lines.append("- 尚未导入两期地块数据。")
    lines += ["", "### 2.4 适宜性评价（模块二）", ""]
    if su.get("stats"):
        for st in su["stats"]:
            lines.append(f"- {st['level']}：{st['count']} 个格网单元")
    else:
        lines.append("- 尚未执行适宜性评价。")

    lines += ["", "## 三、问题识别", ""]
    problems = report.get("problems", [])
    if problems:
        for i, pb in enumerate(problems, 1):
            lines.append(f"{i}. **[{pb['type']}] {pb['title']}** —— {pb['detail']}")
    else:
        lines.append("- 未发现问题。")

    lines += ["", "## 四、原因分析", ""]
    lines += [
        "- 体检结论分布：冲突 %d 宗 / 警告 %d 宗 / 提示 %d 宗 / 通过 %d 宗"
        % (p.get("conflict_count", 0), p.get("by_level", {}).get("警告", 0),
           p.get("by_level", {}).get("提示", 0), p.get("by_level", {}).get("通过", 0)),
        "- 判定依据采用可配置规则矩阵（12 用地大类 × 三区三线，见 `/api/planning/rules`）：",
    ]
    conflict_rows = [r for r in p.get("review_rows", [])
                     if any(o.get("level") == "冲突" for o in r.get("overlaps", []))]
    for r in conflict_rows[:10]:
        for o in r["overlaps"]:
            if o["level"] == "冲突":
                lines.append(f"  - {r['name']}（{r['parcel_code']}，{r['land_use']}）：占用"
                             f"{o.get('zone_type_label', '')} {o['overlap_area_sqm'] / 10000:.2f} 公顷 → 冲突")

    lines += ["", "## 五、规划建议", ""]
    suggestions = report.get("suggestions", [])
    for i, sg in enumerate(suggestions, 1):
        lines.append(f"{i}. **{sg['title']}**：{sg['detail']}")
    if not suggestions:
        lines.append("- 暂无特别建议。")

    lines += ["", "## 六、附录数据表", ""]
    lines += [
        "### 6.1 各类型控制线占用汇总",
        "",
        "| 控制线类型 | 被占用总面积(公顷) |",
        "|---|---:|",
    ]
    if p.get("review_totals"):
        for tt in p["review_totals"]:
            lines.append(f"| {tt['zone_type_label']} | {tt['total_area_sqm'] / 10000:.2f} |")
    else:
        lines.append("| （无占用记录） | 0.00 |")
    lines += ["", "### 6.2 问题台账（前 20 条重叠）", ""]
    lines += ["| 地块 | 用地类型 | 控制线 | 重叠面积(公顷) | 结论 |", "|---|---|---|---:|---|"]
    count = 0
    for r in sorted(p.get("review_rows", []), key=lambda x: -x["total_occupied_sqm"]):
        for o in r.get("overlaps", []):
            if count >= 20:
                break
            lines.append(f"| {r['name']}（{r['parcel_code']}） | {r['land_use']} | "
                         f"{o.get('zone_type_label', '')} | {o['overlap_area_sqm'] / 10000:.2f} | {o['level']} |")
            count += 1
    lines += ["", "### 6.3 设施可达性盲区清单", ""]
    if a["gaps"]:
        lines += ["| 盲区地块 | 用地类型 | 原因 |", "|---|---|---|"]
        for g in a["gaps"]:
            lines.append(f"| {g['name']}（{g['parcel_code']}） | {g['land_use']} | {g['reason']} |")
    else:
        lines.append("- 无盲区。")

    lines += ["", "---", "", "*本报告由 LandVISION 平台自动生成，仅供参考。*"]
    return "\n".join(lines)

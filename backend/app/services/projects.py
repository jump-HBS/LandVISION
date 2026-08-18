# -*- coding: utf-8 -*-
"""
分析项目服务：分析项目的 CRUD、范围统一继承与变更确认。

设计：
  * 分析项目 = 业务上下文（名称 + 基期/末期年份 + 分析范围 GeoJSON，None=全量）；
  * 各分析模块默认继承项目范围；传入子范围时后端校验"必须为项目范围的子集"；
  * 范围变更需前端确认（confirm_scope_change），变更后提示已有结果可能失效。
"""
import json
from typing import Optional

from shapely.geometry import shape

from .. import demo_data
from .spatial import is_demo


def _validate_scope(scope: Optional[dict]):
    """校验范围 GeoJSON 合法性（防前端/测试传参拍平）。"""
    if scope is None:
        return
    try:
        g = shape(scope)
        if g.is_empty:
            raise ValueError("范围几何为空")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"分析范围 GeoJSON 格式非法：{exc}") from exc


# ---------------------------------------------------------------------------
# Demo 模式内存实现（与 PostgreSQL 行为一致）
# ---------------------------------------------------------------------------

def list_projects(db=None) -> list:
    if is_demo():
        return [
            {"id": p["id"], "name": p["name"], "base_year": p["base_year"],
             "current_year": p["current_year"],
             "scope_geojson": p.get("scope_geojson"),
             "created_at": p.get("created_at")}
            for p in demo_data.PROJECTS
        ]
    from ..models import AnalysisProject
    return [
        {"id": r.id, "name": r.name, "base_year": r.base_year,
         "current_year": r.current_year, "scope_geojson": r.scope_geojson,
         "created_at": str(r.created_at) if r.created_at else None}
        for r in db.query(AnalysisProject).order_by(AnalysisProject.id).all()
    ]


def get_project(project_id: int, db=None) -> Optional[dict]:
    if is_demo():
        p = next((x for x in demo_data.PROJECTS if x["id"] == project_id), None)
        return dict(p) if p else None
    from ..models import AnalysisProject
    r = db.query(AnalysisProject).filter(AnalysisProject.id == project_id).first()
    if not r:
        return None
    return {"id": r.id, "name": r.name, "base_year": r.base_year,
            "current_year": r.current_year, "scope_geojson": r.scope_geojson,
            "created_at": str(r.created_at) if r.created_at else None,
            "updated_at": str(r.updated_at) if r.updated_at else None}


def _name_exists(db, name: str, exclude_id: Optional[int] = None) -> bool:
    if is_demo():
        return any(p["name"] == name and p["id"] != exclude_id for p in demo_data.PROJECTS)
    from ..models import AnalysisProject
    q = db.query(AnalysisProject.id).filter(AnalysisProject.name == name)
    if exclude_id:
        q = q.filter(AnalysisProject.id != exclude_id)
    return q.first() is not None


def create_project(db=None, data: dict = None) -> dict:
    data = data or {}
    _validate_scope(data.get("scope"))
    if _name_exists(db, data["name"]):
        raise ValueError(f"项目名称已存在：{data['name']}")
    if is_demo():
        pid = demo_data.next_id(demo_data.PROJECTS)
        demo_data.PROJECTS.append({
            "id": pid, "name": data["name"],
            "base_year": data["base_year"], "current_year": data["current_year"],
            "scope_geojson": data.get("scope"), "created_at": None,
        })
        return get_project(pid)
    from ..models import AnalysisProject
    row = AnalysisProject(
        name=data["name"], base_year=data["base_year"],
        current_year=data["current_year"], scope_geojson=data.get("scope"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_project(row.id, db)


def update_project(project_id: int, db=None, data: dict = None) -> dict:
    """更新项目。范围变更必须 confirm_scope_change=True，否则抛 ValueError。"""
    data = data or {}
    if "scope" in data:
        _validate_scope(data["scope"])
    current = get_project(project_id, db)
    if not current:
        raise ValueError(f"项目不存在：id={project_id}")
    if "name" in data and data["name"] and data["name"] != current["name"] \
            and _name_exists(db, data["name"], exclude_id=project_id):
        raise ValueError(f"项目名称已存在：{data['name']}")

    scope_changed = False
    if "scope" in data:
        new_scope = data["scope"]
        old_scope = current.get("scope_geojson")
        changed = json.dumps(new_scope, sort_keys=True) != json.dumps(old_scope or {}, sort_keys=True)
        if changed and not data.get("confirm_scope_change"):
            raise ValueError("项目范围变更需确认（已有分析结果可能失效，请设置 confirm_scope_change=true）")
        scope_changed = changed

    if is_demo():
        p = next((x for x in demo_data.PROJECTS if x["id"] == project_id), None)
        if "name" in data and data["name"]:
            p["name"] = data["name"]
        if data.get("base_year"):
            p["base_year"] = data["base_year"]
        if data.get("current_year"):
            p["current_year"] = data["current_year"]
        if "scope" in data:
            p["scope_geojson"] = data["scope"]
    else:
        from ..models import AnalysisProject
        row = db.query(AnalysisProject).filter(AnalysisProject.id == project_id).first()
        if data.get("name"):
            row.name = data["name"]
        if data.get("base_year"):
            row.base_year = data["base_year"]
        if data.get("current_year"):
            row.current_year = data["current_year"]
        if "scope" in data:
            row.scope_geojson = data["scope"]
        db.commit()
    result = get_project(project_id, db)
    if scope_changed:
        result["scope_changed"] = True
        result["invalidated"] = ["transition", "suitability", "planning", "accessibility"]
    return result


def delete_project(project_id: int, db=None) -> bool:
    if is_demo():
        before = len(demo_data.PROJECTS)
        demo_data.PROJECTS[:] = [p for p in demo_data.PROJECTS if p["id"] != project_id]
        return len(demo_data.PROJECTS) < before
    from ..models import AnalysisProject
    row = db.query(AnalysisProject).filter(AnalysisProject.id == project_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# 范围校验：子范围必须是项目范围的子集
# ---------------------------------------------------------------------------

def scope_within(sub_scope: dict, project_scope: Optional[dict]) -> bool:
    """判断 sub_scope 是否落在 project_scope 内（项目范围为 None=全量 → 恒 True）。"""
    if not project_scope:
        return True
    if not sub_scope:
        return False
    try:
        sub = shape(sub_scope)
        whole = shape(project_scope)
        diff = sub.difference(whole)
        # 允许极小浮点误差（度²）
        return diff.is_empty or diff.area <= 1e-9
    except Exception:  # noqa: BLE001 —— 几何非法视为不通过
        return False


def resolve_project_scope(db, project_id: Optional[int],
                          requested_scope: Optional[dict]) -> tuple:
    """解析有效分析范围：(scope, project_scope)。

    规则：
      1. 无项目 → 直接用 requested_scope（全量/自定义范围）；
      2. 有项目且未传范围 → 继承项目范围；
      3. 有项目且传了范围 → 校验必须为项目范围子集（不通过抛 ValueError）。
    """
    project_scope = None
    if project_id:
        project = get_project(project_id, db)
        if not project:
            raise ValueError(f"分析项目不存在：id={project_id}")
        project_scope = project.get("scope_geojson")
        if requested_scope and not scope_within(requested_scope, project_scope):
            raise ValueError("传入的分析范围必须与项目范围一致或为其子集")
        if requested_scope is None:
            requested_scope = project_scope
    return requested_scope, project_scope

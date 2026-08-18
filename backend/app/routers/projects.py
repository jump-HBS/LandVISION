# -*- coding: utf-8 -*-
"""路由组：分析项目 projects —— 项目 CRUD（分析业务上下文）。"""
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..schemas import ProjectCreate, ProjectUpdate
from ..services import projects

router = APIRouter(prefix="/projects", tags=["分析项目"])


@router.get("", summary="项目列表")
def list_projects(db=Depends(get_db)):
    return projects.list_projects(db)


@router.post("", summary="新建项目")
def create_project(body: ProjectCreate, db=Depends(get_db)):
    try:
        return projects.create_project(db, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{project_id}", summary="项目详情")
def get_project(project_id: int, db=Depends(get_db)):
    result = projects.get_project(project_id, db)
    if not result:
        raise HTTPException(status_code=404, detail=f"项目不存在：id={project_id}")
    return result


@router.put("/{project_id}", summary="更新项目（范围变更需确认）")
def update_project(project_id: int, body: ProjectUpdate, db=Depends(get_db)):
    try:
        return projects.update_project(project_id, db, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{project_id}", summary="删除项目（其分析结果级联删除）")
def delete_project(project_id: int, db=Depends(get_db)):
    if not projects.delete_project(project_id, db):
        raise HTTPException(status_code=404, detail=f"项目不存在：id={project_id}")
    return {"deleted": project_id}

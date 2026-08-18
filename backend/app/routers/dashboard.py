# -*- coding: utf-8 -*-
"""路由组：数据驾驶舱 dashboard —— 项目工作台统筹汇总（持久化结果优先）。"""
from fastapi import APIRouter, Depends

from ..database import get_db
from ..schemas import DashboardSummaryRequest
from ..services import report_gen

router = APIRouter(prefix="/dashboard", tags=["数据驾驶舱"])


@router.post("/summary", summary="项目工作台统筹汇总（与报告生成共用同一数据源）")
def summary(body: DashboardSummaryRequest, db=Depends(get_db)):
    """按分析项目与范围聚合：持久化结果优先读取各模块数据，
    附加流程进度（模块完成状态）、问题清单与规划建议。"""
    return report_gen.collect_dashboard(
        db, project_id=body.project_id, scope=body.scope, scope_label=body.scope_label,
    )

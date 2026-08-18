# -*- coding: utf-8 -*-
"""路由组：报告 report —— 生成报告 / 下载 Markdown。"""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ..database import get_db
from ..schemas import ReportRequest
from ..services import report_gen

router = APIRouter(prefix="/report", tags=["报告生成"])

_latest: dict | None = None


@router.post("/generate", summary="生成综合分析报告（继承数据驾驶舱的项目与范围）")
def generate(body: ReportRequest, db=Depends(get_db)):
    global _latest
    _latest = report_gen.generate_report(
        db, project_name=body.project_name, period=body.period, author=body.author,
        project_id=body.project_id, scope=body.scope, scope_label=body.scope_label,
    )
    return _latest


@router.get("/latest", summary="获取最近一次生成的报告")
def latest():
    if _latest is None:
        return {"detail": "尚未生成报告，请先调用 POST /api/report/generate"}
    return _latest


@router.get("/latest/download", summary="下载 Markdown 报告", response_class=PlainTextResponse)
def download():
    if _latest is None:
        return PlainTextResponse("尚未生成报告", status_code=404)
    md = report_gen.to_markdown(_latest)
    return PlainTextResponse(
        md,
        headers={"Content-Disposition": 'attachment; filename="landvision_report.md"'},
    )

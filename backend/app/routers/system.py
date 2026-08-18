# -*- coding: utf-8 -*-
"""路由组：系统 system —— 服务信息 / 审计日志查询（运维入口）。"""
import sys
import time

from fastapi import APIRouter, Query

from ..config import settings
from ..database import SessionLocal
from ..middleware import recent_audit

router = APIRouter(prefix="/system", tags=["系统"])

_START_TIME = time.time()


@router.get("/info", summary="服务运行信息")
def system_info():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "mode": "DEMO" if settings.runtime_demo_mode else "POSTGIS",
        "db_connected": SessionLocal is not None,
        "python": sys.version.split()[0],
        "uptime_seconds": int(time.time() - _START_TIME),
    }


@router.get("/audit", summary="最近操作审计日志")
def audit_log(limit: int = Query(50, ge=1, le=500)):
    return {"total": len(recent_audit(limit)), "items": recent_audit(limit)}

# -*- coding: utf-8 -*-
"""
LandVISION 后端入口。

启动时决定运行模式：
  1. 环境变量 LANDVISION_DEMO=0/1 显式指定 → 直接采用；
  2. 未指定 → 尝试连接 PostgreSQL，成功=POSTGIS 模式，失败=DEMO 模式。

启动方式：
  cd backend
  ..\\venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000
  # 或直接：python run.py
"""
import os
from pathlib import Path

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import SessionLocal, init_db_engine
from .errors import register_exception_handlers
from .middleware import (AuditMiddleware, RateLimitMiddleware,
                         RequestIDMiddleware, SecurityHeadersMiddleware)
from .routers import (analysis, dashboard, map_features, parcels, planning, pois,
                      projects, regions, report, system)

# ---------- 日志：控制台 + 审计文件（logs/audit.log） ----------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
file_handler = logging.FileHandler(LOG_DIR / "landvision.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger("landvision")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时探测数据库，决定运行模式。"""
    if settings.demo is True:
        settings.runtime_demo_mode = True
        logger.info(">>> 运行模式：DEMO（环境变量显式指定）")
    elif settings.demo is False:
        ok = init_db_engine()
        settings.runtime_demo_mode = not ok
        logger.info(">>> 运行模式：%s", "POSTGIS（环境变量显式指定）" if ok else "DEMO（连接失败，降级）")
    else:
        ok = init_db_engine()
        settings.runtime_demo_mode = not ok
        logger.info(">>> 运行模式：%s", "POSTGIS（PostgreSQL 连接成功）" if ok else "DEMO（未配置/未连接数据库）")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.description,
    lifespan=lifespan,
)

# ---------- 中间件（顺序：请求ID → 安全头 → 限流 → 审计） ----------
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)

# ---------- CORS（开发期 Vite 代理为主，此为兜底） ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ---------- 统一异常处理 ----------
register_exception_handlers(app)

# ---------- 路由注册 ----------
api_prefix = "/api"
app.include_router(parcels.router, prefix=api_prefix)
app.include_router(pois.router, prefix=api_prefix)
app.include_router(analysis.router, prefix=api_prefix)
app.include_router(planning.router, prefix=api_prefix)
app.include_router(projects.router, prefix=api_prefix)
app.include_router(map_features.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(report.router, prefix=api_prefix)
app.include_router(regions.router, prefix=api_prefix)
app.include_router(system.router, prefix=api_prefix)


@app.get("/", summary="服务信息")
def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "mode": "DEMO" if settings.runtime_demo_mode else "POSTGIS",
        "docs": "/docs",
        "api_prefix": "/api",
    }


@app.get("/healthz", summary="健康检查（供负载均衡/容器探活）")
def healthz():
    # 注意：从模块动态读取 SessionLocal（init_db_engine 在启动时赋值全局变量）
    from . import database as db_module
    return {
        "status": "ok",
        "mode": "DEMO" if settings.runtime_demo_mode else "POSTGIS",
        "db_connected": db_module.SessionLocal is not None,
    }

# -*- coding: utf-8 -*-
"""
数据访问层：SQLAlchemy 引擎与会话管理。

设计要点：
  * 引擎采用"懒初始化"：不连接成功就不创建，应用自动降级到 Demo 模式；
  * get_db() 是 FastAPI 依赖，每个请求一个会话、用后即关；
  * 空间字段由 GeoAlchemy2 的 Geometry 类型支持（见 models.py）。
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import settings

logger = logging.getLogger("landvision.database")

engine = None
SessionLocal: sessionmaker | None = None


def init_db_engine() -> bool:
    """尝试连接配置的 PostgreSQL 数据库。

    返回 True 表示 POSTGIS 模式可用；False 表示连接失败（调用方降级 Demo 模式）。
    """
    global engine, SessionLocal
    try:
        engine = create_engine(
            settings.db_url,
            pool_pre_ping=True,
            # v4.0.3：扩大连接池，避免地图连续请求时连接池耗尽导致的假死
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
            connect_args={"connect_timeout": 3},  # 3 秒连不上立刻放弃，避免启动卡死
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT PostGIS_Version()"))  # 校验 PostGIS 扩展存在
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        logger.info("PostgreSQL + PostGIS 连接成功")
        return True
    except Exception as exc:  # noqa: BLE001 —— 任何连接失败都走降级
        logger.warning("PostgreSQL 连接失败，自动降级 Demo 模式：%s", exc)
        engine = None
        SessionLocal = None
        return False


def get_db():
    """FastAPI 依赖：提供数据库会话，请求结束自动关闭。

    Demo 模式下未初始化引擎（SessionLocal 为 None），直接产出 None，
    服务层据此自动走内存数据分支（spatial.is_demo()）。
    """
    if SessionLocal is None:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

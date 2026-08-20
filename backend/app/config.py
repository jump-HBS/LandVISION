# -*- coding: utf-8 -*-
"""
配置中心（pydantic-settings）：统一从环境变量 / .env 读取，支持多环境。

环境变量前缀 LANDVISION_，例如：
  LANDVISION_DB_URL           → db_url
  LANDVISION_DEMO             → demo（0/1）
  LANDVISION_CORS_ORIGINS     → cors_origins（逗号分隔）
  LANDVISION_RATE_LIMIT       → rate_limit（次/分钟，0=关闭）
  LANDVISION_AUDIT_ENABLED    → audit_enabled
  LANDVISION_MAX_UPLOAD_MB    → max_upload_mb（SHP 上传大小上限）

双模式说明：
  * DEMO 模式（默认）：内存数据 + shapely 运算，无需数据库；
  * POSTGIS 模式：连接 PostgreSQL + PostGIS，空间运算交给数据库；
  * LANDVISION_DEMO 未设置时启动自动探测（连接成功→POSTGIS，失败→DEMO）。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANDVISION_",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 应用 ----------
    app_name: str = "LandVISION API"
    app_version: str = "1.2.0"
    description: str = "国土空间数据管理与智能分析可视化平台 —— 后端服务"

    # ---------- 数据库 ----------
    # 格式：postgresql+psycopg2://用户:密码@主机:端口/库名
    db_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/landvision"

    # 显式指定运行模式（可选）：None 表示启动时自动探测
    demo: bool | None = None

    # ---------- 安全 / 限流 / 上传 ----------
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    )
    rate_limit: int = 300         # 每 IP 每分钟最大请求数，0=关闭（v4.0.3 放宽，避免缩放地图误触限流）
    audit_enabled: bool = True    # 操作审计日志
    max_upload_mb: int = 20       # SHP 压缩包上传大小上限（MB）

    # ---------- v4.0.3 海量数据可视化保护 ----------
    # 单次 GeoJSON 返回要素上限：超过则截断（附 truncated/total），防止数万要素
    # 序列化拖垮后端与前端渲染（地图缩放时按视野加载，超大视野直接跳过）
    max_geojson_features: int = 2000

    # ---------- 演示区（武汉） ----------
    demo_center: tuple = (114.340, 30.500)  # 米→度近似换算基准

    # ---------- 运行时状态（main.py 启动时写入，不由 .env 配置） ----------
    runtime_demo_mode: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

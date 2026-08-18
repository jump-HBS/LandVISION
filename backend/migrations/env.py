# -*- coding: utf-8 -*-
"""Alembic 迁移环境：从应用配置读取数据库地址，导入 ORM 模型供 autogenerate 使用。"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

# 让 backend/ 在 sys.path 中（保证 `import app` 可用）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings          # noqa: E402
from app.models import Base              # noqa: E402
from geoalchemy2 import alembic_helpers  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """优先命令行 -x db_url=xxx，其次环境变量 LANDVISION_DB_URL，最后默认值。"""
    x_args = context.get_x_argument(as_dictionary=True)
    if "db_url" in x_args:
        return x_args["db_url"]
    return settings.db_url


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 不连接数据库（CI / 审查用）。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = create_engine(_database_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

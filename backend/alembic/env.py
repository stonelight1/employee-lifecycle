"""Alembic 环境配置 —— 支持 SQLite batch mode。"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# 将 backend 目录加入 sys.path，确保 app 模块可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import context
from sqlalchemy import engine_from_config, pool

# 导入所有模型以便 Alembic 自动发现
import app.models.employee  # noqa: F401
import app.models.employment  # noqa: F401
import app.models.followup_node  # noqa: F401
import app.models.followup_task  # noqa: F401
import app.models.followup_participant  # noqa: F401
import app.models.communication  # noqa: F401
import app.models.text_version  # noqa: F401
import app.models.ai_summary  # noqa: F401
import app.models.risk  # noqa: F401
import app.models.probation  # noqa: F401
import app.models.regularization  # noqa: F401
import app.models.change  # noqa: F401
import app.models.separation  # noqa: F401
import app.models.todo  # noqa: F401
import app.models.operation_log  # noqa: F401
# 新增模型
import app.models.employee_profile  # noqa: F401
import app.models.attribute_history  # noqa: F401
import app.models.financial_account  # noqa: F401
import app.models.contract  # noqa: F401
import app.models.compensation  # noqa: F401
import app.models.assessment  # noqa: F401
import app.models.note  # noqa: F401
import app.models.separation_checklist  # noqa: F401
import app.models.roster_batch  # noqa: F401
import app.models.roster_row  # noqa: F401
import app.models.roster_issue  # noqa: F401
import app.models.hr_confirmation  # noqa: F401
import app.models.roster_operation  # noqa: F401
import app.models.org_reference  # noqa: F401
import app.models.roster_alias  # noqa: F401
import app.models.roster_value_alias  # noqa: F401
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线迁移模式（只生成 SQL 脚本）。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线迁移模式 —— SQLite 使用 batch mode。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite batch mode
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

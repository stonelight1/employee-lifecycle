"""
统一日志配置。

按 settings.log_dir 输出到文件（按天滚动轮转），同时输出到控制台。
所有 Python 模块通过 `logging.getLogger(__name__)` 获取 logger 即可使用。
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .config import settings


def _resolve_log_dir() -> Path:
    """解析日志目录路径。

    绝对路径按原值使用；相对路径统一基于项目根目录解析。
    默认 LOG_DIR=./logs 时，日志写入 project-root/logs/。
    """
    log_dir = Path(settings.log_dir)
    if log_dir.is_absolute():
        return log_dir

    backend_dir = Path(__file__).resolve().parent.parent
    project_root = backend_dir.parent
    return (project_root / log_dir).resolve()


LOG_DIR = _resolve_log_dir()

# 日志格式
_CONSOLE_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)-35s %(message)s"
_FILE_FORMAT = (
    "%(asctime)s [%(levelname)-7s] %(name)-35s %(module)s:%(lineno)d  %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# level 映射
_LOG_LEVEL = getattr(logging, settings.log_level.upper(), logging.INFO)
_LOGGING_CONFIGURED = False


def setup_logging() -> None:
    """配置全局日志：控制台 + 文件（按天滚动）。"""
    global _LOGGING_CONFIGURED

    # 防止重复调用；不能用 hasHandlers()，否则 uvicorn/pytest 预置 handler
    # 会导致文件日志 handler 被跳过。
    if _LOGGING_CONFIGURED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(_LOG_LEVEL)

    # ── 控制台 Handler ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT, _DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # ── 文件 Handler（按天滚动，保留 30 天）──
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "backend.log"

    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setLevel(_LOG_LEVEL)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, _DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # 记录启动信息
    root_logger.info("=" * 80)
    root_logger.info("日志系统初始化完成")
    root_logger.info("  文件路径 : %s", log_file.resolve())
    root_logger.info("  日志级别 : %s", settings.log_level.upper())
    root_logger.info("  环境     : %s", settings.app_env)
    root_logger.info("=" * 80)
    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger（已配置好父级 handler）。"""
    return logging.getLogger(name)

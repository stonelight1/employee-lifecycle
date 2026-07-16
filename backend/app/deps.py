from __future__ import annotations

from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session as DBSession

from .config import settings
from .database import get_db


def get_current_user() -> dict:
    """
    V1 单用户模式：返回固定本地操作者。

    所有创建、修改、删除、确认、审核和日志均由后端写入固定值。
    前端传入的用户身份字段必须忽略。
    """
    return {
        "user_id": settings.local_operator_id,
        "name": settings.local_operator_name,
    }


def get_db_session(
    db: Generator[DBSession, None, None] = Depends(get_db),
) -> DBSession:
    """获取数据库会话（带 Depends 包装）。"""
    return db

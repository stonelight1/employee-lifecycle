from __future__ import annotations

from typing import Any, ClassVar, Optional

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)

    # SQLite 外键支持在引擎级别设置
    type_annotation_map: ClassVar[dict] = {
        int: sa.Integer,
        float: sa.Float,
        bool: sa.Boolean,
        str: sa.String,
        bytes: sa.LargeBinary,
    }

    def dict(self) -> dict[str, Any]:
        """将模型实例转为字典，排除 None 值以外的全部字段。"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            result[column.name] = value
        return result


class CommonMixin:
    """通用字段 Mixin —— 业务表按需继承。"""

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(sa.String(100), default=None)
    updated_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime, default=None, onupdate=sa.func.now()
    )
    updated_by: Mapped[Optional[str]] = mapped_column(sa.String(100), default=None)
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, nullable=False
    )
    deleted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime, default=None
    )
    deleted_by: Mapped[Optional[str]] = mapped_column(sa.String(100), default=None)


class OperationLogBase(Base):
    """仅供操作日志使用 —— 不包含通用更新/删除字段。"""

    __abstract__ = True

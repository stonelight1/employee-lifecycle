from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OperationLog(Base):
    """
    操作日志 —— 追加写审计表。

    不包含 update / version / is_deleted 等通用业务字段。
    不提供业务接口修改或删除。
    """

    __tablename__ = "operation_log"

    operator_id: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
    operated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    object_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    operation_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    before_data: Mapped[Optional[str]] = mapped_column(sa.Text)
    after_data: Mapped[Optional[str]] = mapped_column(sa.Text)
    operation_source: Mapped[Optional[str]] = mapped_column(sa.String(100))
    business_id: Mapped[Optional[int]] = mapped_column(sa.Integer, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(sa.String(100), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(sa.String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(sa.String(500))

    __table_args__ = (
        sa.Index("ix_oplog_object", "object_type", "object_id"),
    )

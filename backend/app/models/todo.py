from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import TodoStatus
from .base import Base, CommonMixin


class SystemTodo(CommonMixin, Base):
    __tablename__ = "system_todo"

    user_id: Mapped[str] = mapped_column(sa.String(100), nullable=False, index=True)
    business_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    business_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    due_at: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    todo_status: Mapped[TodoStatus] = mapped_column(
        sa.String(30), default=TodoStatus.PENDING, nullable=False
    )
    priority: Mapped[Optional[str]] = mapped_column(sa.String(20))
    source: Mapped[Optional[str]] = mapped_column(sa.String(50))
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        sa.String(200), unique=True
    )

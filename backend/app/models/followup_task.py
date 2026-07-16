from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import ConfirmationMode, FollowupTaskStatus, TaskSource, TriggerType
from .base import Base, CommonMixin


class FollowupTask(CommonMixin, Base):
    __tablename__ = "followup_task"

    employment_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id"), nullable=False, index=True
    )
    node_definition_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("followup_node_definition.id")
    )
    node_version: Mapped[Optional[int]] = mapped_column(sa.Integer)
    node_code_snapshot: Mapped[Optional[str]] = mapped_column(sa.String(50))
    task_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    task_source: Mapped[TaskSource] = mapped_column(
        sa.String(10), default=TaskSource.AUTO, nullable=False
    )
    trigger_type_snapshot: Mapped[Optional[str]] = mapped_column(sa.String(50))
    offset_days_snapshot: Mapped[Optional[int]] = mapped_column(sa.Integer)
    planned_date: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    original_planned_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    date_adjusted_manually: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, nullable=False
    )
    followup_status: Mapped[FollowupTaskStatus] = mapped_column(
        sa.String(30), default=FollowupTaskStatus.PENDING, nullable=False
    )
    confirmation_mode: Mapped[ConfirmationMode] = mapped_column(
        sa.String(10), default=ConfirmationMode.ALL, nullable=False
    )
    completed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    completed_by: Mapped[Optional[str]] = mapped_column(sa.String(100))
    cancel_reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        sa.String(200), unique=True
    )

    employment = relationship("EmploymentRecord", backref="followup_tasks")

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import RosterRowStatus, ImportAction, ReviewStatus, ExecutionStatus
from .base import Base


class RosterImportRow(Base):
    __tablename__ = "roster_import_row"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_batch.id"), nullable=False, index=True
    )
    row_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    normalized_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    match_type: Mapped[Optional[str]] = mapped_column(sa.String(50))
    row_status: Mapped[RosterRowStatus] = mapped_column(
        sa.String(30), default=RosterRowStatus.NEW, nullable=False
    )
    # 三个独立状态字段（新逻辑）
    import_action: Mapped[Optional[ImportAction]] = mapped_column(
        sa.String(15), nullable=True, default=None
    )
    review_status: Mapped[Optional[ReviewStatus]] = mapped_column(
        sa.String(25), nullable=True, default=None
    )
    execution_status: Mapped[Optional[ExecutionStatus]] = mapped_column(
        sa.String(15), nullable=True, default=None
    )
    lifecycle_decision_json: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    raw_data_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    normalized_data_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    diff_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    planned_actions_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    result_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime, default=None, onupdate=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("batch_id", "row_no", name="uq_roster_row_batch_row"),
        sa.Index("ix_roster_row_batch_status", "batch_id", "row_status"),
        sa.Index("ix_roster_row_execution", "batch_id", "execution_status"),
        sa.Index("ix_roster_row_review", "batch_id", "review_status"),
    )

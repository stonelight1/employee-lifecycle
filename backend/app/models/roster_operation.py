from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RosterImportOperation(Base):
    __tablename__ = "roster_import_operation"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_batch.id"), nullable=False, index=True
    )
    row_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_row.id")
    )
    employee_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    operation_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    target_table: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    target_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    before_snapshot_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    after_snapshot_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    reversible: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    irreversible_reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("ix_roster_operation_batch", "batch_id"),
        sa.Index("ix_roster_operation_employee", "employee_id"),
    )

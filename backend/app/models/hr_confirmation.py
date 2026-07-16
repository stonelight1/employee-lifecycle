from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import ConfirmationItemStatus
from .base import Base


class HrConfirmationItem(Base):
    __tablename__ = "hr_confirmation_item"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    employment_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id")
    )
    source_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(sa.String(100))
    issue_code: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    before_data_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    after_data_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    import_batch_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    import_row_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    item_status: Mapped[ConfirmationItemStatus] = mapped_column(
        sa.String(15), default=ConfirmationItemStatus.PENDING, nullable=False
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )
    handled_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

    __table_args__ = (
        sa.Index("ix_hr_confirmation_status", "item_status"),
        sa.Index("ix_hr_confirmation_employee", "employee_id", "item_status"),
        sa.Index("ix_hr_confirmation_batch", "import_batch_id", "item_status"),
    )

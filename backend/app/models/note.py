from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import AttributeSource
from .base import Base


class EmployeeNote(Base):
    __tablename__ = "employee_note"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    employment_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id")
    )
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_type: Mapped[AttributeSource] = mapped_column(
        sa.String(20), default=AttributeSource.MANUAL, nullable=False
    )
    source_id: Mapped[Optional[str]] = mapped_column(sa.String(100))
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_batch.id")
    )
    source_row_no: Mapped[Optional[int]] = mapped_column(sa.Integer)
    content_hash: Mapped[Optional[str]] = mapped_column(sa.String(64))
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )

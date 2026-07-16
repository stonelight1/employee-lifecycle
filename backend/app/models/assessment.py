from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EmployeeAssessment(Base):
    __tablename__ = "employee_assessment"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    assessment_type: Mapped[str] = mapped_column(
        sa.String(10), nullable=False
    )
    result_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    attachment_path: Mapped[Optional[str]] = mapped_column(sa.String(500))
    assessment_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    source_type: Mapped[Optional[str]] = mapped_column(
        sa.String(20), default="MANUAL"
    )
    import_batch_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )

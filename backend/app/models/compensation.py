from __future__ import annotations

from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import AttributeSource, SalaryType
from .base import Base


class CompensationRecord(Base):
    __tablename__ = "compensation_record"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    employment_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id"), index=True
    )
    raw_salary_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    salary_type: Mapped[Optional[str]] = mapped_column(
        sa.String(10), default=SalaryType.UNKNOWN
    )
    base_salary: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 2))
    probation_salary: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 2))
    regular_salary: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 2))
    daily_rate: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 2))
    performance_amount: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(12, 2))
    performance_ratio: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    commission_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    other_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    effective_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    source_type: Mapped[Optional[str]] = mapped_column(
        sa.String(20), default=AttributeSource.MANUAL
    )
    import_batch_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("ix_compensation_employee_effective", "employee_id", "employment_id", "effective_date"),
    )

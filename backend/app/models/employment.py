from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import EmploymentStatus, ProbationStatus
from .base import Base, CommonMixin


class EmploymentRecord(CommonMixin, Base):
    __tablename__ = "employment_record"

    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    employment_seq: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        sa.String(30), default=EmploymentStatus.PENDING, nullable=False
    )
    hire_date: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    probation_start_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    probation_end_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    probation_status: Mapped[ProbationStatus] = mapped_column(
        sa.String(30), default=ProbationStatus.NOT_STARTED, nullable=False
    )
    department: Mapped[Optional[str]] = mapped_column(sa.String(200))
    position: Mapped[Optional[str]] = mapped_column(sa.String(200))
    manager_name: Mapped[Optional[str]] = mapped_column(sa.String(100))
    regularization_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    separation_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    date_rule_source: Mapped[Optional[str]] = mapped_column(sa.String(50))
    probation_end_date_source: Mapped[Optional[str]] = mapped_column(sa.String(50))

    __table_args__ = (
        sa.UniqueConstraint("employee_id", "employment_seq", name="uq_employee_seq"),
    )

    employee = relationship("Employee", backref="employment_records")

    @property
    def current_employment_constraint(self) -> sa.Index:
        """同一员工最多一条 PENDING/ACTIVE/SEPARATING 的有效任职。"""
        return sa.Index(
            "ix_active_employment",
            "employee_id",
            sqlite_where=sa.and_(
                EmploymentRecord.employment_status.in_(
                    [EmploymentStatus.PENDING, EmploymentStatus.ACTIVE, EmploymentStatus.SEPARATING]
                ),
                EmploymentRecord.is_deleted == False,
            ),
            unique=True,
        )

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import EmployeeStatus, ProfileCompleteness
from .base import Base, CommonMixin


class Employee(CommonMixin, Base):
    __tablename__ = "employee"

    employee_no: Mapped[Optional[str]] = mapped_column(sa.String(50), index=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        sa.String(100), nullable=False, index=True
    )
    mobile: Mapped[Optional[str]] = mapped_column(sa.String(30))
    email: Mapped[Optional[str]] = mapped_column(sa.String(200))
    source_employee_key: Mapped[Optional[str]] = mapped_column(sa.String(200))
    employee_status: Mapped[EmployeeStatus] = mapped_column(
        sa.String(30), default=EmployeeStatus.ACTIVE, nullable=False
    )
    source: Mapped[Optional[str]] = mapped_column(sa.String(100))
    profile_completeness_status: Mapped[Optional[ProfileCompleteness]] = mapped_column(
        sa.String(20), default=ProfileCompleteness.COMPLETE
    )

    __table_args__ = (
        sa.Index(
            "uq_normalized_name_active",
            "normalized_name",
            unique=True,
            sqlite_where=sa.text(
                "is_deleted = 0 AND employee_status != 'ENTRY_ERROR'"
            ),
        ),
    )

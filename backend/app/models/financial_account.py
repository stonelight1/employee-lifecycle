from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import AccountStatus, AccountType, AttributeSource
from .base import Base, CommonMixin


class EmployeeFinancialAccount(CommonMixin, Base):
    __tablename__ = "employee_financial_account"

    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    account_type: Mapped[AccountType] = mapped_column(
        sa.String(10), nullable=False
    )
    account_no: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    bank_name: Mapped[Optional[str]] = mapped_column(sa.String(200))
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(
        sa.String(10), default=AccountStatus.ACTIVE, nullable=False
    )
    source_type: Mapped[AttributeSource] = mapped_column(
        sa.String(20), default=AttributeSource.MANUAL, nullable=False
    )
    confirmed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

    __table_args__ = (
        sa.Index("ix_financial_account_employee", "employee_id", "account_type", "account_status"),
    )

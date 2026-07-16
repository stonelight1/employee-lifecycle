from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import AttributeSource, ContractType
from .base import Base, CommonMixin


class EmploymentContract(CommonMixin, Base):
    __tablename__ = "employment_contract"

    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    employment_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id"), index=True
    )
    contract_status: Mapped[Optional[str]] = mapped_column(sa.String(50))
    signing_company: Mapped[Optional[str]] = mapped_column(sa.String(200))
    contract_type: Mapped[Optional[ContractType]] = mapped_column(
        sa.String(20), default=ContractType.UNKNOWN
    )
    start_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    signing_sequence: Mapped[Optional[int]] = mapped_column(sa.Integer)
    source_type: Mapped[AttributeSource] = mapped_column(
        sa.String(20), default=AttributeSource.MANUAL, nullable=False
    )
    confirmed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

    __table_args__ = (
        sa.Index("ix_contract_employee_employment", "employee_id", "employment_id"),
    )

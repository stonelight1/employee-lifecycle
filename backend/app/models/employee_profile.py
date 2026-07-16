from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import AttributeSource
from .base import Base, CommonMixin


class EmployeeProfile(CommonMixin, Base):
    __tablename__ = "employee_profile"

    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, unique=True, index=True
    )
    identity_card: Mapped[Optional[str]] = mapped_column(sa.String(50))
    gender: Mapped[Optional[str]] = mapped_column(sa.String(10))
    birth_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    household_registration: Mapped[Optional[str]] = mapped_column(sa.String(500))
    residence_address: Mapped[Optional[str]] = mapped_column(sa.String(500))
    household_type: Mapped[Optional[str]] = mapped_column(sa.String(100))
    graduation_school: Mapped[Optional[str]] = mapped_column(sa.String(200))
    major: Mapped[Optional[str]] = mapped_column(sa.String(200))
    education_level: Mapped[Optional[str]] = mapped_column(sa.String(50))
    social_insurance_policy: Mapped[Optional[str]] = mapped_column(sa.String(50))
    housing_fund_policy: Mapped[Optional[str]] = mapped_column(sa.String(50))
    social_insurance_status: Mapped[Optional[str]] = mapped_column(sa.String(200))
    housing_fund_status: Mapped[Optional[str]] = mapped_column(sa.String(200))
    social_insurance_start_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    housing_fund_start_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    benefit_raw_text: Mapped[Optional[str]] = mapped_column(sa.Text)

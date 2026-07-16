from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import AttributeSource
from .base import Base, CommonMixin


class EmployeeAttributeHistory(CommonMixin, Base):
    __tablename__ = "employee_attribute_history"

    employee_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employee.id"), nullable=False, index=True
    )
    employment_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id")
    )
    category: Mapped[Optional[str]] = mapped_column(sa.String(50))
    field_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    before_value_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    after_value_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    effective_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    source_type: Mapped[AttributeSource] = mapped_column(
        sa.String(20), default=AttributeSource.MANUAL, nullable=False
    )
    source_id: Mapped[Optional[str]] = mapped_column(sa.String(100))
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_batch.id")
    )
    operator_name: Mapped[Optional[str]] = mapped_column(sa.String(100))

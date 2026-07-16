from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CommonMixin


class EmploymentChange(CommonMixin, Base):
    __tablename__ = "employment_change"

    employment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("employment_record.id"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(
        sa.String(30), nullable=False
    )  # DEPARTMENT | POSITION | MANAGER
    effective_date: Mapped[sa.Date] = mapped_column(sa.Date, nullable=False)
    before_data: Mapped[Optional[str]] = mapped_column(sa.Text)
    after_data: Mapped[Optional[str]] = mapped_column(sa.Text)
    reason: Mapped[Optional[str]] = mapped_column(sa.String(500))
    confirmed_by: Mapped[Optional[str]] = mapped_column(sa.String(100))
    confirmed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

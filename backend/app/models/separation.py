from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CommonMixin


class SeparationRecord(CommonMixin, Base):
    __tablename__ = "separation_record"

    employment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("employment_record.id"),
        nullable=False,
        index=True,
    )
    planned_separation_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    actual_separation_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    separation_type: Mapped[Optional[str]] = mapped_column(sa.String(50))
    reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    hr_comment: Mapped[Optional[str]] = mapped_column(sa.Text)
    confirmed_by: Mapped[Optional[str]] = mapped_column(sa.String(100))
    confirmed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

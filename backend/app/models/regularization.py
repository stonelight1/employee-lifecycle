from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CommonMixin


class RegularizationRecord(CommonMixin, Base):
    __tablename__ = "regularization_record"

    employment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("employment_record.id"),
        nullable=False,
        index=True,
    )
    probation_review_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("probation_review.id")
    )
    decision: Mapped[str] = mapped_column(
        sa.String(30), nullable=False
    )  # APPROVED | EXTENDED | NOT_APPROVED
    effective_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    new_probation_end_date: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    decision_reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    ai_summary_version_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("ai_summary_version.id")
    )
    confirmed_by: Mapped[Optional[str]] = mapped_column(sa.String(100))
    confirmed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    is_effective: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, nullable=False
    )

    employment = relationship("EmploymentRecord", backref="regularization_records")

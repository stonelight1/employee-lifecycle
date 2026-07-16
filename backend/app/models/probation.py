from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CommonMixin


class ProbationReview(CommonMixin, Base):
    __tablename__ = "probation_review"

    employment_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("employment_record.id"),
        nullable=False,
        index=True,
    )
    followup_task_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("followup_task.id")
    )
    communication_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("communication_record.id")
    )
    review_seq: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    review_stage: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )  # FOLLOWUP | FINAL
    review_status: Mapped[Optional[str]] = mapped_column(sa.String(30))
    hr_evaluation: Mapped[Optional[str]] = mapped_column(sa.Text)
    employee_feedback: Mapped[Optional[str]] = mapped_column(sa.Text)
    recommendation: Mapped[Optional[str]] = mapped_column(sa.String(500))
    reviewed_by: Mapped[Optional[str]] = mapped_column(sa.String(100))
    reviewed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

    employment = relationship("EmploymentRecord", backref="probation_reviews")

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import AssessmentSource, RiskLevel, RiskReviewStatus
from .base import Base, CommonMixin


class RiskAssessment(CommonMixin, Base):
    __tablename__ = "risk_assessment"

    communication_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("communication_record.id"),
        nullable=False,
        index=True,
    )
    source_text_version_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    ai_summary_version_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("ai_summary_version.id")
    )
    assessment_source: Mapped[AssessmentSource] = mapped_column(
        sa.String(10), default=AssessmentSource.AI, nullable=False
    )
    ai_risk_level: Mapped[Optional[RiskLevel]] = mapped_column(
        sa.String(20), default=RiskLevel.UNSPECIFIED
    )
    ai_risk_reasons: Mapped[Optional[str]] = mapped_column(sa.Text)
    ai_evidence: Mapped[Optional[str]] = mapped_column(sa.Text)
    ai_followup_suggestions: Mapped[Optional[str]] = mapped_column(sa.Text)
    risk_review_status: Mapped[RiskReviewStatus] = mapped_column(
        sa.String(30), default=RiskReviewStatus.PENDING_REVIEW, nullable=False
    )
    hr_risk_level: Mapped[Optional[RiskLevel]] = mapped_column(sa.String(20))
    hr_comment: Mapped[Optional[str]] = mapped_column(sa.Text)
    reviewed_by: Mapped[Optional[str]] = mapped_column(sa.String(100))
    reviewed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    is_current: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    communication = relationship("CommunicationRecord", backref="risk_assessments")

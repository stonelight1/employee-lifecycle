from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import CommunicationStatus
from .base import Base, CommonMixin


class CommunicationRecord(CommonMixin, Base):
    __tablename__ = "communication_record"

    employment_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("employment_record.id"), nullable=False, index=True
    )
    followup_task_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("followup_task.id")
    )
    communication_type: Mapped[Optional[str]] = mapped_column(sa.String(50))
    communication_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    hr_user_id: Mapped[Optional[str]] = mapped_column(sa.String(100))
    communication_status: Mapped[CommunicationStatus] = mapped_column(
        sa.String(30), default=CommunicationStatus.DRAFT, nullable=False
    )
    current_text_version_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    current_text_version_no: Mapped[Optional[int]] = mapped_column(sa.Integer)
    current_text_hash: Mapped[Optional[str]] = mapped_column(sa.String(64))
    manual_summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    hr_conclusion: Mapped[Optional[str]] = mapped_column(sa.Text)
    source: Mapped[Optional[str]] = mapped_column(sa.String(50))

    employment = relationship("EmploymentRecord", backref="communication_records")
    followup_task = relationship("FollowupTask", backref="communication_records")

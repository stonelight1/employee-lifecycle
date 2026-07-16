from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import SummaryStatus
from .base import Base, CommonMixin


class AiSummaryVersion(CommonMixin, Base):
    __tablename__ = "ai_summary_version"

    communication_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("communication_record.id"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_text_version_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    source_text_version_no: Mapped[Optional[int]] = mapped_column(sa.Integer)
    source_text_hash: Mapped[Optional[str]] = mapped_column(sa.String(64))
    provider: Mapped[Optional[str]] = mapped_column(sa.String(100))
    model_name: Mapped[Optional[str]] = mapped_column(sa.String(100))
    prompt_version: Mapped[Optional[str]] = mapped_column(sa.String(50))
    prompt_snapshot: Mapped[Optional[str]] = mapped_column(sa.Text)
    output_schema_version: Mapped[Optional[str]] = mapped_column(sa.String(50))
    summary_status: Mapped[SummaryStatus] = mapped_column(
        sa.String(30), default=SummaryStatus.PROCESSING, nullable=False
    )
    structured_summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    raw_response_ref: Mapped[Optional[str]] = mapped_column(sa.String(500))
    is_ai_suggestion: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, nullable=False
    )
    is_current: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    is_stale: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    started_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    finished_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    failure_type: Mapped[Optional[str]] = mapped_column(sa.String(50))
    failure_reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        sa.String(200), unique=True
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "communication_id", "version_no", name="uq_ai_summary_version"
        ),
    )

    communication = relationship("CommunicationRecord", backref="ai_summary_versions")

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import IssueSeverity, ResolutionStatus
from .base import Base


class RosterImportIssue(Base):
    __tablename__ = "roster_import_issue"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_batch.id"), nullable=False, index=True
    )
    row_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("roster_import_row.id")
    )
    employee_id: Mapped[Optional[int]] = mapped_column(sa.Integer)
    field_key: Mapped[Optional[str]] = mapped_column(sa.String(100))
    issue_code: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(
        sa.String(10), nullable=False, default=IssueSeverity.WARNING
    )
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(sa.Text)
    old_value_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    new_value_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    allowed_actions_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    resolution_status: Mapped[ResolutionStatus] = mapped_column(
        sa.String(15), default=ResolutionStatus.PENDING, nullable=False
    )
    resolution_action: Mapped[Optional[str]] = mapped_column(sa.String(50))
    resolution_value_json: Mapped[Optional[str]] = mapped_column(sa.Text)
    resolution_note: Mapped[Optional[str]] = mapped_column(sa.Text)
    resolved_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime, default=None, onupdate=sa.func.now()
    )

    # 关系
    row: Mapped[Optional["RosterImportRow"]] = relationship(
        "RosterImportRow", lazy="joined"
    )

    __table_args__ = (
        sa.Index("ix_roster_issue_batch_status", "batch_id", "resolution_status"),
    )

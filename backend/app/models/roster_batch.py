from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import RosterBatchStatus, RosterImportMode
from .base import Base, CommonMixin


class RosterImportBatch(CommonMixin, Base):
    __tablename__ = "roster_import_batch"

    batch_no: Mapped[str] = mapped_column(sa.String(50), nullable=False, unique=True)
    mode: Mapped[RosterImportMode] = mapped_column(
        sa.String(15), nullable=False, default=RosterImportMode.SYNC
    )
    file_name: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    stored_file_path: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    file_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    sheet_name: Mapped[Optional[str]] = mapped_column(sa.String(200))
    header_row: Mapped[str] = mapped_column(sa.Text, default="[]")
    batch_status: Mapped[RosterBatchStatus] = mapped_column(
        sa.String(30), default=RosterBatchStatus.UPLOADED, nullable=False
    )
    header_row_index: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    column_mappings_json: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    total_rows: Mapped[int] = mapped_column(sa.Integer, default=0)
    new_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    update_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    confirmation_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    warning_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    error_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    imported_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    started_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    completed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    failed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    failure_message: Mapped[Optional[str]] = mapped_column(sa.Text)
    rolled_back_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)

    __table_args__ = (
        sa.Index("ix_roster_batch_sha256", "file_sha256"),
        sa.Index("ix_roster_batch_status", "batch_status"),
    )

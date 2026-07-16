from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import ChecklistItemType, ChecklistItemType
from .base import Base, CommonMixin


class SeparationChecklistItem(CommonMixin, Base):
    __tablename__ = "separation_checklist_item"

    separation_record_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("separation_record.id"), nullable=False, index=True
    )
    item_type: Mapped[ChecklistItemType] = mapped_column(
        sa.String(30), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    completed: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    remark: Mapped[Optional[str]] = mapped_column(sa.Text)

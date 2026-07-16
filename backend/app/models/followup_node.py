from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import ConfirmationMode, TriggerType
from .base import Base, CommonMixin


class FollowupNodeDefinition(CommonMixin, Base):
    __tablename__ = "followup_node_definition"

    node_code: Mapped[str] = mapped_column(sa.String(50), nullable=False, unique=True)
    node_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    trigger_type: Mapped[TriggerType] = mapped_column(
        sa.String(50), default=TriggerType.DAYS_AFTER_HIRE, nullable=False
    )
    offset_days: Mapped[Optional[int]] = mapped_column(sa.Integer)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    default_assignee_rule: Mapped[Optional[str]] = mapped_column(sa.String(200))
    confirmation_mode: Mapped[ConfirmationMode] = mapped_column(
        sa.String(10), default=ConfirmationMode.ALL, nullable=False
    )
    node_version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    effective_from: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    effective_to: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)

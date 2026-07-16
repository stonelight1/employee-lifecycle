from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import ConfirmationStatus, ParticipantRole
from .base import Base


class FollowupTaskParticipant(Base):
    __tablename__ = "followup_task_participant"

    task_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("followup_task.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    participant_role: Mapped[ParticipantRole] = mapped_column(
        sa.String(30), default=ParticipantRole.PARTICIPANT, nullable=False
    )
    active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    assigned_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )
    removed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    created_by: Mapped[Optional[str]] = mapped_column(sa.String(100))

    __table_args__ = (
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_participant"),
    )


class FollowupTaskConfirmation(Base):
    __tablename__ = "followup_task_confirmation"

    task_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("followup_task.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    confirmation_status: Mapped[ConfirmationStatus] = mapped_column(
        sa.String(30), default=ConfirmationStatus.PENDING, nullable=False
    )
    comment: Mapped[Optional[str]] = mapped_column(sa.Text)
    confirmed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime)
    request_id: Mapped[Optional[str]] = mapped_column(sa.String(200))
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "task_id", "user_id", "request_id", name="uq_task_confirmation"
        ),
    )

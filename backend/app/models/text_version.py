from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class CommunicationTextVersion(Base):
    __tablename__ = "communication_text_version"

    communication_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("communication_record.id"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    text_hash: Mapped[Optional[str]] = mapped_column(sa.String(64))
    text_length: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(sa.String(500))
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, default=sa.func.now(), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(sa.String(100))

    __table_args__ = (
        sa.UniqueConstraint(
            "communication_id", "version_no", name="uq_comm_text_version"
        ),
    )

    communication = relationship("CommunicationRecord", backref="text_versions")

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CommonMixin


class RosterValueAlias(CommonMixin, Base):
    __tablename__ = "roster_value_alias"

    field_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    source_value_normalized: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    target_value: Mapped[str] = mapped_column(sa.String(200), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "field_key", "source_value_normalized", name="uq_roster_value_alias"
        ),
    )

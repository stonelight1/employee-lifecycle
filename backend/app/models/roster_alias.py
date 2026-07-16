from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CommonMixin


class RosterColumnAlias(CommonMixin, Base):
    __tablename__ = "roster_column_alias"

    source_header_normalized: Mapped[str] = mapped_column(
        sa.String(200), nullable=False, unique=True
    )
    target_field_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

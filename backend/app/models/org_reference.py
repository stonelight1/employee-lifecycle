from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import OrgRefType
from .base import Base, CommonMixin


class OrganizationReference(CommonMixin, Base):
    __tablename__ = "organization_reference"

    reference_type: Mapped[OrgRefType] = mapped_column(
        sa.String(15), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

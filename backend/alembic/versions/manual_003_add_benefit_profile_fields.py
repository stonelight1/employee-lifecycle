"""add benefit profile fields

Revision ID: manual_003
Revises: manual_002
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "manual_003"
down_revision: Union[str, None] = "manual_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("employee_profile", schema=None) as batch_op:
        batch_op.add_column(sa.Column("social_insurance_policy", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("housing_fund_policy", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("social_insurance_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("housing_fund_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("benefit_raw_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employee_profile", schema=None) as batch_op:
        batch_op.drop_column("benefit_raw_text")
        batch_op.drop_column("housing_fund_start_date")
        batch_op.drop_column("social_insurance_start_date")
        batch_op.drop_column("housing_fund_policy")
        batch_op.drop_column("social_insurance_policy")

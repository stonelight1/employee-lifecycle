"""添加业务索引以优化 N+1 查询

Revision ID: add_business_indexes
Revises: e51167fb8da7
Create Date: 2026-07-16 08:25:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_business_indexes"
down_revision: Union[str, None] = "e51167fb8da7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_risk_comm_current_created
        ON risk_assessment(communication_id, is_deleted, is_current, created_at, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_emp_employee_status_deleted
        ON employment_record(employee_id, employment_status, is_deleted)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_task_employment_status_planned
        ON followup_task(employment_id, followup_status, is_deleted, planned_date, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_comm_employment_status_created
        ON communication_record(employment_id, is_deleted, communication_status, created_at, id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_comm_employment_status_created")
    op.execute("DROP INDEX IF EXISTS idx_task_employment_status_planned")
    op.execute("DROP INDEX IF EXISTS idx_emp_employee_status_deleted")
    op.execute("DROP INDEX IF EXISTS idx_risk_comm_current_created")

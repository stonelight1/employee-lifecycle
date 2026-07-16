"""v0.5.0: 花名册行状态拆分

1. roster_import_row 增加 import_action / review_status / execution_status
2. roster_import_row 增加 lifecycle_decision_json
3. enums 增加 ImportAction / ReviewStatus / ExecutionStatus
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "manual_005_roster_status_split"
down_revision: str = "manual_004_roster_import_fix"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    # === roster_import_row 增加新状态字段 ===
    op.add_column(
        "roster_import_row",
        sa.Column("import_action", sa.String(15), nullable=True),
    )
    op.add_column(
        "roster_import_row",
        sa.Column("review_status", sa.String(25), nullable=True),
    )
    op.add_column(
        "roster_import_row",
        sa.Column("execution_status", sa.String(15), nullable=True),
    )
    op.add_column(
        "roster_import_row",
        sa.Column("lifecycle_decision_json", sa.Text, nullable=True),
    )

    # 新增索引
    op.create_index(
        "ix_roster_row_execution",
        "roster_import_row",
        ["batch_id", "execution_status"],
    )
    op.create_index(
        "ix_roster_row_review",
        "roster_import_row",
        ["batch_id", "review_status"],
    )

    # === 回填已有数据 ===
    # row_status -> import_action + review_status + execution_status 映射
    connection = op.get_bind()
    connection.execute(
        sa.text("""
        UPDATE roster_import_row
        SET
            import_action = CASE
                WHEN row_status IN ('NEW', 'UPDATE', 'UNCHANGED') THEN row_status
                WHEN row_status = 'NEEDS_CONFIRMATION' THEN 'UPDATE'
                WHEN row_status = 'ERROR' THEN 'NEW'
                WHEN row_status IN ('SKIPPED', 'IMPORTED') THEN NULL
            END,
            review_status = CASE
                WHEN row_status IN ('NEW', 'UPDATE', 'UNCHANGED') THEN 'CLEAN'
                WHEN row_status = 'NEEDS_CONFIRMATION' THEN 'NEEDS_CONFIRMATION'
                WHEN row_status = 'ERROR' THEN 'ERROR'
                WHEN row_status = 'SKIPPED' THEN 'IGNORED'
                WHEN row_status = 'IMPORTED' THEN 'CLEAN'
            END,
            execution_status = CASE
                WHEN row_status = 'SKIPPED' THEN 'SKIPPED'
                WHEN row_status = 'IMPORTED' THEN 'IMPORTED'
                ELSE 'PENDING'
            END
        WHERE row_status IS NOT NULL
        """),
    )


def downgrade() -> None:
    op.drop_index("ix_roster_row_execution", table_name="roster_import_row")
    op.drop_index("ix_roster_row_review", table_name="roster_import_row")
    op.drop_column("roster_import_row", "execution_status")
    op.drop_column("roster_import_row", "review_status")
    op.drop_column("roster_import_row", "import_action")
    op.drop_column("roster_import_row", "lifecycle_decision_json")

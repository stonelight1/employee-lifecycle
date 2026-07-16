"""v0.4.5: 花名册导入修复迁移

1. hr_confirmation_item 增加 import_batch_id / import_row_id
2. roster_import_batch 拆分 header_row 为 header_row_index + column_mappings_json
"""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

revision: str = "manual_004_roster_import_fix"
down_revision: str = "manual_003"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    # === hr_confirmation_item ===
    op.add_column(
        "hr_confirmation_item",
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "hr_confirmation_item",
        sa.Column("import_row_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_hr_confirmation_batch",
        "hr_confirmation_item",
        ["import_batch_id", "item_status"],
    )

    # === roster_import_batch ===
    op.add_column(
        "roster_import_batch",
        sa.Column("header_row_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "roster_import_batch",
        sa.Column("column_mappings_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # SQLite 不直接支持 DROP COLUMN，用 batch 模式
    # === roster_import_batch ===
    with op.batch_alter_table("roster_import_batch") as batch_op:
        batch_op.drop_column("column_mappings_json")
        batch_op.drop_column("header_row_index")

    # === hr_confirmation_item ===
    with op.batch_alter_table("hr_confirmation_item") as batch_op:
        batch_op.drop_index("ix_hr_confirmation_batch")
        batch_op.drop_column("import_row_id")
        batch_op.drop_column("import_batch_id")

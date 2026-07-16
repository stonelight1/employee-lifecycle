"""添加花名册导入相关表和业务规则修正字段

- 新增 15 张表
- employee 新增字段和索引
- employment_record 新增字段

Revision ID: manual_002
Revises: add_business_indexes
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "manual_002"
down_revision: Union[str, None] = "add_business_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================
    # employee 表新增字段和索引
    # =========================
    with op.batch_alter_table("employee", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("profile_completeness_status", sa.String(20), nullable=True)
        )
        batch_op.create_index(
            "uq_normalized_name_active",
            ["normalized_name"],
            unique=True,
            sqlite_where=sa.text("is_deleted = 0 AND employee_status != 'ENTRY_ERROR'"),
        )

    # =========================
    # employment_record 新增字段
    # =========================
    with op.batch_alter_table("employment_record", schema=None) as batch_op:
        batch_op.add_column(sa.Column("expected_hire_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("actual_hire_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("probation_months", sa.Integer(), nullable=False, server_default=sa.text("3"))
        )
        batch_op.add_column(sa.Column("expected_regularization_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("actual_regularization_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("employment_type", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("work_city", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("work_mode", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("team_name", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("status_before_separating", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("hire_cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("hire_cancel_reasons_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("hire_cancel_note", sa.String(500), nullable=True))

    # =========================
    # 新增表：employee_profile
    # =========================
    op.create_table(
        "employee_profile",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("identity_card", sa.String(50), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("household_registration", sa.String(500), nullable=True),
        sa.Column("residence_address", sa.String(500), nullable=True),
        sa.Column("household_type", sa.String(100), nullable=True),
        sa.Column("graduation_school", sa.String(200), nullable=True),
        sa.Column("major", sa.String(200), nullable=True),
        sa.Column("education_level", sa.String(50), nullable=True),
        sa.Column("social_insurance_status", sa.String(200), nullable=True),
        sa.Column("housing_fund_status", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", name="uq_employee_profile_employee"),
    )
    with op.batch_alter_table("employee_profile", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employee_profile_employee_id"), ["employee_id"], unique=False)

    # =========================
    # 新增表：employee_attribute_history
    # =========================
    op.create_table(
        "employee_attribute_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("before_value_json", sa.Text(), nullable=True),
        sa.Column("after_value_json", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("employee_attribute_history", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employee_attribute_history_employee_id"), ["employee_id"], unique=False)

    # =========================
    # 新增表：employee_financial_account
    # =========================
    op.create_table(
        "employee_financial_account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("account_type", sa.String(10), nullable=False),
        sa.Column("account_no", sa.String(200), nullable=False),
        sa.Column("bank_name", sa.String(200), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("account_status", sa.String(10), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("employee_financial_account", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employee_financial_account_employee_id"), ["employee_id"], unique=False)
        batch_op.create_index("ix_financial_account_employee", ["employee_id", "account_type", "account_status"], unique=False)

    # =========================
    # 新增表：employment_contract
    # =========================
    op.create_table(
        "employment_contract",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.Column("contract_status", sa.String(50), nullable=True),
        sa.Column("signing_company", sa.String(200), nullable=True),
        sa.Column("contract_type", sa.String(20), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("signing_sequence", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("employment_contract", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employment_contract_employee_id"), ["employee_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_employment_contract_employment_id"), ["employment_id"], unique=False)
        batch_op.create_index("ix_contract_employee_employment", ["employee_id", "employment_id"], unique=False)

    # =========================
    # 新增表：compensation_record
    # =========================
    op.create_table(
        "compensation_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.Column("raw_salary_text", sa.Text(), nullable=True),
        sa.Column("salary_type", sa.String(10), nullable=True),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("probation_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("regular_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("daily_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("performance_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("performance_ratio", sa.Numeric(5, 2), nullable=True),
        sa.Column("commission_text", sa.Text(), nullable=True),
        sa.Column("other_text", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("compensation_record", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_compensation_record_employee_id"), ["employee_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_compensation_record_employment_id"), ["employment_id"], unique=False)
        batch_op.create_index("ix_compensation_employee_effective", ["employee_id", "employment_id", "effective_date"], unique=False)

    # =========================
    # 新增表：employee_assessment
    # =========================
    op.create_table(
        "employee_assessment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("assessment_type", sa.String(10), nullable=False),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("attachment_path", sa.String(500), nullable=True),
        sa.Column("assessment_date", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("employee_assessment", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employee_assessment_employee_id"), ["employee_id"], unique=False)

    # =========================
    # 新增表：employee_note
    # =========================
    op.create_table(
        "employee_note",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("source_row_no", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("employee_note", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employee_note_employee_id"), ["employee_id"], unique=False)

    # =========================
    # 新增表：separation_checklist_item
    # =========================
    op.create_table(
        "separation_checklist_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("separation_record_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["separation_record_id"], ["separation_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("separation_checklist_item", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_separation_checklist_item_separation_record_id"), ["separation_record_id"], unique=False)

    # =========================
    # 新增表：organization_reference
    # =========================
    op.create_table(
        "organization_reference",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference_type", sa.String(15), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # =========================
    # 新增表：roster_import_batch
    # =========================
    op.create_table(
        "roster_import_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_no", sa.String(50), nullable=False),
        sa.Column("mode", sa.String(15), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("stored_file_path", sa.String(1000), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.String(200), nullable=True),
        sa.Column("header_row", sa.Text(), nullable=False),
        sa.Column("batch_status", sa.String(30), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("update_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("confirmation_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_no"),
    )
    with op.batch_alter_table("roster_import_batch", schema=None) as batch_op:
        batch_op.create_index("ix_roster_batch_sha256", ["file_sha256"], unique=False)
        batch_op.create_index("ix_roster_batch_status", ["batch_status"], unique=False)

    # =========================
    # 新增表：roster_import_row
    # =========================
    op.create_table(
        "roster_import_row",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("match_type", sa.String(50), nullable=True),
        sa.Column("row_status", sa.String(30), nullable=False),
        sa.Column("raw_data_json", sa.Text(), nullable=True),
        sa.Column("normalized_data_json", sa.Text(), nullable=True),
        sa.Column("diff_json", sa.Text(), nullable=True),
        sa.Column("planned_actions_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["roster_import_batch.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "row_no", name="uq_roster_row_batch_row"),
    )
    with op.batch_alter_table("roster_import_row", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_roster_import_row_batch_id"), ["batch_id"], unique=False)
        batch_op.create_index("ix_roster_row_batch_status", ["batch_id", "row_status"], unique=False)

    # =========================
    # 新增表：roster_import_issue
    # =========================
    op.create_table(
        "roster_import_issue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("field_key", sa.String(100), nullable=True),
        sa.Column("issue_code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("old_value_json", sa.Text(), nullable=True),
        sa.Column("new_value_json", sa.Text(), nullable=True),
        sa.Column("allowed_actions_json", sa.Text(), nullable=True),
        sa.Column("resolution_status", sa.String(15), nullable=False),
        sa.Column("resolution_action", sa.String(50), nullable=True),
        sa.Column("resolution_value_json", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["roster_import_batch.id"]),
        sa.ForeignKeyConstraint(["row_id"], ["roster_import_row.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("roster_import_issue", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_roster_import_issue_batch_id"), ["batch_id"], unique=False)
        batch_op.create_index("ix_roster_issue_batch_status", ["batch_id", "resolution_status"], unique=False)

    # =========================
    # 新增表：hr_confirmation_item
    # =========================
    op.create_table(
        "hr_confirmation_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("issue_code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("before_data_json", sa.Text(), nullable=True),
        sa.Column("after_data_json", sa.Text(), nullable=True),
        sa.Column("item_status", sa.String(15), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["employment_id"], ["employment_record.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("hr_confirmation_item", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_hr_confirmation_item_employee_id"), ["employee_id"], unique=False)
        batch_op.create_index("ix_hr_confirmation_status", ["item_status"], unique=False)
        batch_op.create_index("ix_hr_confirmation_employee", ["employee_id", "item_status"], unique=False)

    # =========================
    # 新增表：roster_import_operation
    # =========================
    op.create_table(
        "roster_import_operation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("target_table", sa.String(50), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("before_snapshot_json", sa.Text(), nullable=True),
        sa.Column("after_snapshot_json", sa.Text(), nullable=True),
        sa.Column("reversible", sa.Boolean(), nullable=False),
        sa.Column("irreversible_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["roster_import_batch.id"]),
        sa.ForeignKeyConstraint(["row_id"], ["roster_import_row.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("roster_import_operation", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_roster_import_operation_batch_id"), ["batch_id"], unique=False)
        batch_op.create_index("ix_roster_operation_employee", ["employee_id"], unique=False)

    # =========================
    # 新增表：roster_column_alias
    # =========================
    op.create_table(
        "roster_column_alias",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_header_normalized", sa.String(200), nullable=False),
        sa.Column("target_field_key", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_header_normalized"),
    )

    # =========================
    # 新增表：roster_value_alias
    # =========================
    op.create_table(
        "roster_value_alias",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("source_value_normalized", sa.String(200), nullable=False),
        sa.Column("target_value", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_key", "source_value_normalized", name="uq_roster_value_alias"),
    )

    # =========================
    # 更新现有的数据库数据
    # =========================
    # employment_record: 迁移现有 hire_date 数据到新字段
    # PENDING: expected_hire_date = hire_date, actual_hire_date = NULL
    op.execute(
        "UPDATE employment_record SET expected_hire_date = hire_date, actual_hire_date = NULL "
        "WHERE employment_status = 'PENDING' AND expected_hire_date IS NULL"
    )
    # ACTIVE/SEPARATING/SEPARATED: actual_hire_date = hire_date, expected_hire_date = hire_date
    op.execute(
        "UPDATE employment_record SET actual_hire_date = hire_date, expected_hire_date = hire_date "
        "WHERE employment_status IN ('ACTIVE', 'SEPARATING', 'SEPARATED') "
        "AND actual_hire_date IS NULL"
    )
    # probation_months: 设为默认 3
    op.execute(
        "UPDATE employment_record SET probation_months = 3 WHERE probation_months IS NULL"
    )


def downgrade() -> None:
    # 注意：降级可能导致数据丢失，但这是有意的——回退到旧模型结构
    # 删除新增表（逆序）
    op.drop_table("roster_value_alias")
    op.drop_table("roster_column_alias")
    with op.batch_alter_table("roster_import_operation", schema=None) as batch_op:
        batch_op.drop_index("ix_roster_operation_employee")
        batch_op.drop_index(batch_op.f("ix_roster_import_operation_batch_id"))
    op.drop_table("roster_import_operation")
    with op.batch_alter_table("hr_confirmation_item", schema=None) as batch_op:
        batch_op.drop_index("ix_hr_confirmation_employee")
        batch_op.drop_index("ix_hr_confirmation_status")
        batch_op.drop_index(batch_op.f("ix_hr_confirmation_item_employee_id"))
    op.drop_table("hr_confirmation_item")
    with op.batch_alter_table("roster_import_issue", schema=None) as batch_op:
        batch_op.drop_index("ix_roster_issue_batch_status")
        batch_op.drop_index(batch_op.f("ix_roster_import_issue_batch_id"))
    op.drop_table("roster_import_issue")
    with op.batch_alter_table("roster_import_row", schema=None) as batch_op:
        batch_op.drop_index("ix_roster_row_batch_status")
        batch_op.drop_index(batch_op.f("ix_roster_import_row_batch_id"))
    op.drop_table("roster_import_row")
    with op.batch_alter_table("roster_import_batch", schema=None) as batch_op:
        batch_op.drop_index("ix_roster_batch_status")
        batch_op.drop_index("ix_roster_batch_sha256")
    op.drop_table("roster_import_batch")
    op.drop_table("organization_reference")
    with op.batch_alter_table("separation_checklist_item", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_separation_checklist_item_separation_record_id"))
    op.drop_table("separation_checklist_item")
    with op.batch_alter_table("employee_note", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_employee_note_employee_id"))
    op.drop_table("employee_note")
    with op.batch_alter_table("employee_assessment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_employee_assessment_employee_id"))
    op.drop_table("employee_assessment")
    with op.batch_alter_table("compensation_record", schema=None) as batch_op:
        batch_op.drop_index("ix_compensation_employee_effective")
        batch_op.drop_index(batch_op.f("ix_compensation_record_employment_id"))
        batch_op.drop_index(batch_op.f("ix_compensation_record_employee_id"))
    op.drop_table("compensation_record")
    with op.batch_alter_table("employment_contract", schema=None) as batch_op:
        batch_op.drop_index("ix_contract_employee_employment")
        batch_op.drop_index(batch_op.f("ix_employment_contract_employment_id"))
        batch_op.drop_index(batch_op.f("ix_employment_contract_employee_id"))
    op.drop_table("employment_contract")
    with op.batch_alter_table("employee_financial_account", schema=None) as batch_op:
        batch_op.drop_index("ix_financial_account_employee")
        batch_op.drop_index(batch_op.f("ix_employee_financial_account_employee_id"))
    op.drop_table("employee_financial_account")
    with op.batch_alter_table("employee_attribute_history", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_employee_attribute_history_employee_id"))
    op.drop_table("employee_attribute_history")
    with op.batch_alter_table("employee_profile", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_employee_profile_employee_id"))
    op.drop_table("employee_profile")

    # 移除 employment_record 新增字段
    with op.batch_alter_table("employment_record", schema=None) as batch_op:
        batch_op.drop_column("hire_cancel_note")
        batch_op.drop_column("hire_cancel_reasons_json")
        batch_op.drop_column("hire_cancelled_at")
        batch_op.drop_column("status_before_separating")
        batch_op.drop_column("team_name")
        batch_op.drop_column("work_mode")
        batch_op.drop_column("work_city")
        batch_op.drop_column("employment_type")
        batch_op.drop_column("actual_regularization_date")
        batch_op.drop_column("expected_regularization_date")
        batch_op.drop_column("probation_months")
        batch_op.drop_column("actual_hire_date")
        batch_op.drop_column("expected_hire_date")

    # 移除 employee 新增字段和索引
    with op.batch_alter_table("employee", schema=None) as batch_op:
        batch_op.drop_index("uq_normalized_name_active")
        batch_op.drop_column("profile_completeness_status")

"""花名册导入提交服务 —— 执行实际业务数据写入。

核心原则：
1. CONFIRM_BEFORE_UPDATE 字段：提交时绝不修改业务数据，只创建 HR 确认事项。
2. APPEND_RECORD 字段：提交时不创建业务记录，只创建 HR 确认事项。
3. 缺少入职日期：仍创建员工档案，标记不完整，创建提醒，不创建任职。
4. 不可自动转正或自动入职 —— 必须经 HR 确认。
5. 所有业务写入在单个数据库事务中完成。
6. 失败时全部回滚，FAILED 状态在独立事务中保存。
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    AccountStatus,
    AccountType,
    AssessmentType,
    AttributeSource,
    ConfirmationIssueCode,
    ContractType,
    EmployeeStatus,
    EmploymentStatus,
    EmploymentType,
    ExecutionStatus,
    FieldUpdateMode,
    ImportAction,
    IssueSeverity,
    ProbationStatus,
    ProfileCompleteness,
    RosterBatchStatus,
    RosterImportMode,
    RosterRowStatus,
    SalaryType,
    WorkMode,
)
from ..exceptions import (
    Conflict,
    InvalidStateTransition,
    ResourceNotFound,
    ValidationError,
)
from ..models import (
    Employee,
    EmployeeProfile,
    EmploymentRecord,
    FollowupTask,
    HrConfirmationItem,
    RosterImportBatch,
    RosterImportIssue,
    RosterImportOperation,
    RosterImportRow,
)
from ..models.attribute_history import EmployeeAttributeHistory
from ..models.assessment import EmployeeAssessment
from ..models.change import EmploymentChange
from ..models.compensation import CompensationRecord
from ..models.contract import EmploymentContract
from ..models.financial_account import EmployeeFinancialAccount
from ..models.followup_node import FollowupNodeDefinition
from ..models.note import EmployeeNote
from ..services import operation_log_service
from ..services.employee_service import create_employee, normalize_name
from ..services.employment_service import calculate_probation_end_date

from .roster_field_policy import (
    FieldUpdateMode as PolicyMode,
    get_all_field_keys,
    get_auto_update_fields,
    get_confirmation_fields,
    get_append_fields,
    get_field_policy,
)
from .roster_lifecycle_evaluator import evaluate_roster_lifecycle
from .salary_parser import parse_salary_text
from .benefit_parser import BENEFIT_PROFILE_FIELDS

# ============================================================
# 字段分类（使用统一策略）
# ============================================================

# 自动更新字段 —— 无需 HR 确认即可直接应用
AUTO_UPDATE_FIELDS: set[str] = get_auto_update_fields()

# 需 HR 确认的字段 —— 变更时仅生成确认项，不修改业务数据
CONFIRMATION_FIELDS: set[str] = get_confirmation_fields()

# 追加记录字段 —— 提交时不创建业务记录，只创建确认项
APPEND_RECORD_FIELDS: set[str] = get_append_fields()

# Employee 表可更新字段
_EMPLOYEE_AUTO_FIELDS: set[str] = {
    "mobile", "email", "employee_no",
    "source",
}

# EmploymentRecord 表自动更新字段
_EMPLOYMENT_AUTO_FIELDS: set[str] = {
    "department", "position", "manager_name", "team_name",
    "employment_type", "work_city", "work_mode",
}

# EmployeeProfile 表自动更新字段
_PROFILE_AUTO_FIELDS: set[str] = {
    "household_registration", "residence_address", "household_type",
    "graduation_school", "major", "education_level",
    "social_insurance_status", "housing_fund_status",
    "social_insurance_policy", "housing_fund_policy",
    "social_insurance_start_date", "housing_fund_start_date",
    "benefit_raw_text",
}

_BENEFIT_CLEARABLE_FIELDS: set[str] = {
    "social_insurance_start_date",
    "housing_fund_start_date",
}

# 任职变更字段到变更类型的映射（SYNC 模式使用）
_EMPLOYMENT_CHANGE_TYPE_MAP: dict[str, str] = {
    "department": "DEPARTMENT",
    "position": "POSITION",
    "team_name": "TEAM",
    "manager_name": "MANAGER",
}

# ============================================================
# 公共入口
# ============================================================


def commit_import(
    db: DBSession,
    batch_id: int,
    operator: dict,
) -> dict:
    """执行花名册导入提交。

    所有业务写入在单个数据库事务中完成。
    任何失败都必须引发异常，由调用方负责回滚事务和更新批次状态。

    Args:
        db: 数据库会话。
        batch_id: 导入批次 ID。
        operator: 操作人信息，至少包含 user_id。

    Returns:
        {batch_id, batch_no, status, summary}

    Raises:
        ResourceNotFound: 批次不存在。
        InvalidStateTransition: 批次状态不是 READY。
        Conflict: 乐观锁冲突。
    """
    batch = _get_batch_or_error(db, batch_id)

    if _enum_value(batch.batch_status) != RosterBatchStatus.READY.value:
        raise InvalidStateTransition(
            f"批次状态 {_enum_value(batch.batch_status)} 不允许提交，仅 READY 状态可提交"
        )

    # 乐观锁：递增 version，用条件更新检测并发修改
    original_version = batch.version
    new_version = (batch.version or 0) + 1

    affected = (
        db.query(RosterImportBatch)
        .filter(
            RosterImportBatch.id == batch_id,
            RosterImportBatch.version == original_version,
        )
        .update({"version": new_version})
    )
    if affected == 0:
        raise Conflict("批次数据已被其他操作修改，请刷新后重试")

    batch.version = new_version

    # 查询待处理行
    rows = _load_processable_rows(db, batch_id)

    # 批量加载已匹配员工（减少 N+1 查询）
    matched_employee_ids = [
        r.employee_id for r in rows if r.employee_id is not None
    ]
    employee_cache: dict[int, Employee] = {}
    if matched_employee_ids:
        employees = (
            db.query(Employee)
            .filter(
                Employee.id.in_(matched_employee_ids),
                Employee.is_deleted == False,
            )
            .all()
        )
        employee_cache = {e.id: e for e in employees}

    summary = {
        "total": len(rows),
        "created_count": 0,
        "updated_count": 0,
        "unchanged_count": 0,
        "skipped_count": 0,
        "cooperation_skipped_count": 0,
        "confirmation_count": 0,
        "incomplete_profile_count": 0,
        "employment_change_count": 0,
        "compensation_count": 0,
        "note_count": 0,
        "failed_count": 0,
    }

    try:
        for row in rows:
            action = _parse_planned_action(row)
            if _enum_value(row.row_status) == RosterRowStatus.SKIPPED.value:
                _process_skip_row(db, row, operator)
                summary["skipped_count"] += 1
                if action.get("reason_code") == "REGION_COOPERATION":
                    summary["cooperation_skipped_count"] += 1
                continue

            if _enum_value(row.row_status) == RosterRowStatus.UNCHANGED.value:
                summary["unchanged_count"] += 1
                row.row_status = RosterRowStatus.IMPORTED
                row.import_action = ImportAction.UNCHANGED
                row.execution_status = ExecutionStatus.IMPORTED
                row.review_status = "CLEAN"
                db.flush()
                continue

            if _enum_value(row.row_status) == RosterRowStatus.NEW.value:
                result = _process_new_row(
                    db, row, batch_id, batch.mode, operator,
                )
                summary["created_count"] += 1
                if result.get("action") == "created_incomplete":
                    summary["incomplete_profile_count"] += 1
                if result.get("confirmations_created", 0) > 0:
                    summary["confirmation_count"] += result["confirmations_created"]

            elif _enum_value(row.row_status) in (
                RosterRowStatus.UPDATE.value,
                RosterRowStatus.NEEDS_CONFIRMATION.value,
            ):
                employee_id = _resolve_employee_id(row, employee_cache)
                result = _process_update_row(
                    db, row, employee_id, batch_id, batch.mode, operator,
                )
                if result.get("action") == "updated":
                    summary["updated_count"] += 1
                confirmations = result.get("confirmations_created", 0)
                if confirmations > 0:
                    summary["confirmation_count"] += confirmations

        # 更新批次为成功
        now = datetime.now()
        batch.batch_status = RosterBatchStatus.SUCCEEDED
        batch.completed_at = now
        batch.imported_count = summary["created_count"] + summary["updated_count"]
        batch.skipped_count = summary["skipped_count"]
        # 更新批次统计字段
        batch.new_count = summary["created_count"]
        batch.update_count = summary["updated_count"]
        batch.unchanged_count = summary["unchanged_count"]
        batch.confirmation_count = summary["confirmation_count"]
        db.flush()

    except Exception as e:
        # 在回滚的事务中设置 FAILED 是无效的 ——
        # 由调用方（路由层）负责在独立事务中保存失败状态
        now = datetime.now()
        batch.batch_status = RosterBatchStatus.FAILED
        batch.failed_at = now
        batch.failure_message = str(e)
        db.flush()
        raise

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "status": _enum_value(batch.batch_status),
        "message": "导入已完成",
        "summary": summary,
    }


# ============================================================
# 行处理 —— 新增
# ============================================================


def _process_new_row(
    db: DBSession,
    row: RosterImportRow,
    batch_id: int,
    mode: RosterImportMode,
    operator: dict,
) -> dict:
    """处理新增行。

    规则：
    - 缺少入职日期：仍创建员工档案，标记不完整，不创建任职。
      创建 MISSING_HIRE_DATE 确认提醒。
    - 使用统一生命周期评估器决定转正状态。
    """
    data = _parse_row_data(row)

    if not data.get("name"):
        raise ValidationError(f"行 {row.row_no} 缺少员工姓名")

    today = date.today()
    operator_id = operator.get("user_id", "system")

    # ── 0. 获取或计算生命周期决策 ──
    lifecycle = _get_lifecycle_decision(row, data, mode)
    is_regularized = lifecycle.get("probation_status") == ProbationStatus.REGULARIZED.value
    actual_reg_date = _parse_optional_date(lifecycle.get("actual_regularization_date"))
    expected_reg_date = _parse_optional_date(lifecycle.get("expected_regularization_date"))
    prob_status = ProbationStatus(lifecycle.get("probation_status", ProbationStatus.IN_PROGRESS.value))
    emp_status_value = EmploymentStatus(lifecycle.get("employment_status", EmploymentStatus.ACTIVE.value))
    prob_months = lifecycle.get("probation_months", 3)
    should_create_tasks = lifecycle.get("should_create_probation_tasks", not is_regularized)

    # ── 1. 创建 Employee ──
    emp_data = {
        "name": data["name"],
        "employee_no": data.get("employee_no"),
        "mobile": data.get("mobile"),
        "email": data.get("email"),
        "source": "ROSTER_IMPORT",
    }
    employee = create_employee(db, emp_data, operator)
    employee_id = employee["id"]

    _write_operation(
        db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
        operation_type="CREATE_EMPLOYEE", target_table="employee",
        target_id=employee_id, before=None, after=employee, reversible=True,
    )

    # ── 2. 创建 EmployeeProfile ──
    profile_data = _extract_profile_data(data)
    for field in ("identity_card", "birth_date", "gender"):
        if field in data and data.get(field) is not None:
            if field == "birth_date":
                profile_data[field] = _parse_optional_date(data[field])
            else:
                profile_data[field] = data[field]
    if profile_data:
        _create_profile(db, employee_id, profile_data, operator)
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_PROFILE", target_table="employee_profile",
            target_id=employee_id, before=None, after=profile_data, reversible=True,
        )

    # ── 3. 检查入职日期 ──
    hire_date = data.get("hire_date")
    if not hire_date:
        _set_profile_incomplete(db, employee_id)
        _create_hr_confirmation(
            db=db, employee_id=employee_id, employment_id=None,
            issue_code=ConfirmationIssueCode.MISSING_HIRE_DATE,
            title="缺少入职日期",
            description=f"员工「{data['name']}」缺少入职日期，请补充后系统将自动创建任职记录。",
            before=None, after=None,
            import_batch_id=batch_id, import_row_id=row.id,
        )

        row.employee_id = employee_id
        row.row_status = RosterRowStatus.IMPORTED
        row.import_action = ImportAction.NEW
        row.execution_status = ExecutionStatus.IMPORTED
        row.review_status = "NEEDS_CONFIRMATION"
        db.flush()
        return {"employee_id": employee_id, "employment_id": None, "action": "created_incomplete", "confirmations_created": 1}

    if not isinstance(hire_date, date):
        try:
            hire_date = date.fromisoformat(str(hire_date))
        except (ValueError, TypeError):
            raise ValidationError(f"行 {row.row_no} 入职日期格式无效: {hire_date}")

    # ── 4. 设置试用期起止日期 ──
    probation_end = None
    probation_start = None
    if prob_status in (ProbationStatus.IN_PROGRESS, ProbationStatus.REGULARIZED):
        probation_end = calculate_probation_end_date(hire_date, prob_months)
        probation_start = hire_date

    # ── 5. 检查是否已有有效任职 ──
    existing_active = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.employment_status.in_(
                [
                    EmploymentStatus.PENDING,
                    EmploymentStatus.ACTIVE,
                    EmploymentStatus.SEPARATING,
                ]
            ),
            EmploymentRecord.is_deleted == False,
        )
        .first()
    )

    if existing_active:
        employment = existing_active
        for field in _EMPLOYMENT_AUTO_FIELDS:
            if field in data:
                setattr(employment, field, data[field])
        employment.updated_by = operator_id
        db.flush()
    else:
        max_seq = (
            db.query(EmploymentRecord.employment_seq)
            .filter(EmploymentRecord.employee_id == employee_id)
            .order_by(EmploymentRecord.employment_seq.desc())
            .first()
        )
        employment_seq = (max_seq[0] if max_seq else 0) + 1

        employment = EmploymentRecord(
            employee_id=employee_id,
            employment_seq=employment_seq,
            employment_status=emp_status_value,
            hire_date=hire_date,
            actual_hire_date=hire_date if emp_status_value != EmploymentStatus.PENDING else None,
            probation_start_date=probation_start,
            probation_end_date=probation_end,
            probation_status=prob_status,
            probation_months=prob_months,
            actual_regularization_date=actual_reg_date,
            expected_regularization_date=expected_reg_date,
            regularization_date=actual_reg_date or expected_reg_date,
            department=data.get("department"),
            position=data.get("position"),
            manager_name=data.get("manager_name"),
            team_name=data.get("team_name"),
            employment_type=data.get("employment_type", EmploymentType.FORMAL),
            work_city=data.get("work_city"),
            work_mode=data.get("work_mode", WorkMode.UNKNOWN),
            date_rule_source="AUTO",
            probation_end_date_source="AUTO",
            created_by=operator_id,
        )
        db.add(employment)
        db.flush()

    employment_id = employment.id

    _write_operation(
        db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
        operation_type="CREATE_EMPLOYMENT", target_table="employment_record",
        target_id=employment_id, before=None, after=employment.dict(),
        reversible=True,
    )

    # ── 6. INITIALIZE 模式生成跟进任务 ──
    if _enum_value(mode) == RosterImportMode.INITIALIZE.value and should_create_tasks:
        _generate_initialization_tasks(db, employment_id, hire_date)

    # ── 7. 创建 Contract（仅 NEW 行直接创建）──
    contract_data = _extract_contract_data(data)
    if contract_data:
        contract = EmploymentContract(
            employee_id=employee_id,
            employment_id=employment_id,
            contract_status=contract_data.get("contract_status"),
            signing_company=contract_data.get("signing_company"),
            contract_type=contract_data.get("contract_type", ContractType.UNKNOWN),
            start_date=contract_data.get("start_date"),
            end_date=contract_data.get("end_date"),
            source_type=AttributeSource.ROSTER_IMPORT,
            created_by=operator_id,
        )
        db.add(contract)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_CONTRACT", target_table="employment_contract",
            target_id=contract.id, before=None, after=contract.dict(),
            reversible=True,
        )

    # ── 8. 创建 FinancialAccount（NEW 行直接创建）──
    account_data = _extract_account_data(data)
    seen_types: set[str] = set()
    for acct in account_data:
        acct_type = acct["account_type"].value
        if acct_type in seen_types:
            continue
        seen_types.add(acct_type)

        account = EmployeeFinancialAccount(
            employee_id=employee_id,
            account_type=acct["account_type"],
            account_no=acct["account_no"],
            bank_name=acct.get("bank_name"),
            is_primary=(acct_type == "BANK" and len(seen_types) <= 2),
            account_status=AccountStatus.ACTIVE,
            source_type=AttributeSource.ROSTER_IMPORT,
            created_by=operator_id,
        )
        db.add(account)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_FINANCIAL_ACCOUNT",
            target_table="employee_financial_account",
            target_id=account.id, before=None, after=account.dict(),
            reversible=True,
        )

    # ── 9. 创建 Compensation ──
    salary_data = _extract_salary_data(data)
    if salary_data:
        comp = CompensationRecord(
            employee_id=employee_id,
            employment_id=employment_id,
            **salary_data,
            source_type=AttributeSource.ROSTER_IMPORT,
            import_batch_id=batch_id,
            effective_date=hire_date,
        )
        db.add(comp)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_COMPENSATION",
            target_table="compensation_record",
            target_id=comp.id, before=None, after=comp.dict(),
            reversible=True,
        )

    # ── 10. 创建 Assessment ──
    for assess in _extract_assessment_data(data):
        assessment = EmployeeAssessment(
            employee_id=employee_id,
            assessment_type=assess["assessment_type"],
            result_text=assess.get("result_text"),
            source_type=AttributeSource.ROSTER_IMPORT,
            import_batch_id=batch_id,
        )
        db.add(assessment)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_ASSESSMENT",
            target_table="employee_assessment",
            target_id=assessment.id, before=None, after=assessment.dict(),
            reversible=True,
        )

    # ── 11. 创建 Note ──
    _create_note_if_needed(db, data, employee_id, employment_id, batch_id, row.id, row.row_no)

    # ── 12. 创建生命周期确认事项 ──
    lifecycle_conf_count = _create_lifecycle_confirmations(
        db, employee_id, employment_id,
        lifecycle.get("issues", []),
        batch_id, row.id,
    )

    # ── 13. 更新行状态 ──
    row.employee_id = employee_id
    row.row_status = RosterRowStatus.IMPORTED
    row.import_action = ImportAction.NEW
    row.execution_status = ExecutionStatus.IMPORTED
    # 如果有待确认事项，标记审核状态
    if lifecycle_conf_count > 0:
        row.review_status = "PENDING"
    else:
        row.review_status = "CLEAN"
    db.flush()

    return {
        "employee_id": employee_id,
        "employment_id": employment_id,
        "action": "created",
        "confirmations_created": lifecycle_conf_count,
    }


# ============================================================
# 行处理 —— 更新
# ============================================================


def _process_update_row(
    db: DBSession,
    row: RosterImportRow,
    employee_id: int,
    batch_id: int,
    mode: RosterImportMode,
    operator: dict,
) -> dict:
    """处理更新行。

    核心原则（P0）：
    - CONFIRM_BEFORE_UPDATE 字段：仅创建确认事项，绝不修改业务数据。
    - APPEND_RECORD 字段：仅创建确认事项，绝不创建业务记录。
    - AUTO_UPDATE 字段：直接更新业务数据。
    """
    data = _parse_row_data(row)
    diff = _parse_diff(row)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or employee.is_deleted:
        raise ResourceNotFound(f"待更新员工 {employee_id} 不存在或已删除")

    employment = _find_current_employment(db, employee_id)
    confirmations_created = 0
    operator_id = operator.get("user_id", "system")

    # ── 1. 更新 Employee 自动更新字段 ──
    emp_before: dict[str, Any] = {}
    emp_updates: dict[str, Any] = {}
    for field in _EMPLOYEE_AUTO_FIELDS:
        if field not in data or field not in diff:
            continue
        old_val = getattr(employee, field, None)
        new_val = data[field]
        if new_val is not None and new_val != old_val:
            # 确认字段不得直接修改 —— 交给确认事项
            policy = get_field_policy(field)
            if policy and policy.update_mode == FieldUpdateMode.CONFIRM_BEFORE_UPDATE:
                _create_field_confirmation(
                    db, employee_id, None, field, old_val, new_val, batch_id, row.id,
                )
                confirmations_created += 1
                continue

            # 自动更新字段直接应用
            emp_before[field] = old_val
            emp_updates[field] = new_val
            setattr(employee, field, new_val)

            _create_attribute_history(
                db=db, employee_id=employee_id, employment_id=None,
                field_name=field, before=old_val, after=new_val,
                source=AttributeSource.ROSTER_IMPORT, batch_id=batch_id,
                operator=operator,
            )

    if emp_updates:
        employee.updated_by = operator_id
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="UPDATE_EMPLOYEE", target_table="employee",
            target_id=employee_id, before=emp_before, after=emp_updates,
            reversible=True,
        )

    # ── 2. Profile 字段处理 ──
    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id == employee_id,
    ).first()
    profile_data = _extract_profile_data(data)

    if not profile and profile_data:
        profile = _create_profile(db, employee_id, profile_data, operator)
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id,
            employee_id=employee_id, operation_type="CREATE_PROFILE",
            target_table="employee_profile", target_id=profile.id,
            before=None, after=profile_data,
            reversible=True,
        )

    if profile and profile_data:
        profile_before: dict[str, Any] = {}
        profile_updates: dict[str, Any] = {}
        for field, value in profile_data.items():
            if value is None and field not in _BENEFIT_CLEARABLE_FIELDS:
                continue
            old_val = getattr(profile, field, None)
            if _values_equal(value, old_val):
                continue

            policy = get_field_policy(field)
            if policy and policy.update_mode == FieldUpdateMode.CONFIRM_BEFORE_UPDATE:
                # 确认字段：仅创建确认事项，不修改业务数据
                _create_field_confirmation(
                    db, employee_id, None, field, old_val, value, batch_id, row.id,
                )
                confirmations_created += 1
                continue

            # 自动更新字段直接应用
            profile_before[field] = old_val
            profile_updates[field] = value
            setattr(profile, field, value)

            _create_attribute_history(
                db=db, employee_id=employee_id, employment_id=None,
                field_name=f"profile.{field}", before=old_val, after=value,
                source=AttributeSource.ROSTER_IMPORT, batch_id=batch_id,
                operator=operator,
            )

        if profile_updates:
            db.flush()
            _write_operation(
                db=db, batch_id=batch_id, row_id=row.id,
                employee_id=employee_id, operation_type="UPDATE_PROFILE",
                target_table="employee_profile", target_id=employee_id,
                before=profile_before, after=profile_updates,
                reversible=True,
            )

    # ── 2b. 检查确认字段（不在 profile_data 中但在 data 中有变化的字段）──
    # identity_card, birth_date, gender 等不通过 _extract_profile_data 提取，
    # 需要单独检查
    _confirmation_profile_fields = {"identity_card", "birth_date", "gender"}
    for field in _confirmation_profile_fields:
        if field not in data or field not in diff:
            continue
        old_val = getattr(profile, field, None) if profile else None
        new_val = data.get(field)
        if new_val is not None and not _values_equal(new_val, old_val):
            _create_field_confirmation(
                db, employee_id, None, field, old_val, new_val, batch_id, row.id,
            )
            confirmations_created += 1

    # ── 3. Employment 自动更新字段 ──
    if employment:
        emp_change_fields: dict[str, dict[str, Any]] = {}
        for field in _EMPLOYMENT_AUTO_FIELDS:
            if field not in data or field not in diff:
                continue
            old_val = getattr(employment, field, None)
            new_val = data[field]
            if new_val is not None and not _values_equal(new_val, old_val):
                emp_change_fields[field] = {"before": old_val, "after": new_val}

        if emp_change_fields:
            if _enum_value(mode) == RosterImportMode.INITIALIZE.value:
                for field, change in emp_change_fields.items():
                    setattr(employment, field, change["after"])
                employment.updated_by = operator_id
                db.flush()
                _write_operation(
                    db=db, batch_id=batch_id, row_id=row.id,
                    employee_id=employee_id,
                    operation_type="UPDATE_EMPLOYMENT",
                    target_table="employment_record",
                    target_id=employment.id,
                    before={k: v["before"] for k, v in emp_change_fields.items()},
                    after={k: v["after"] for k, v in emp_change_fields.items()},
                    reversible=True,
                )
            else:
                for field, change in emp_change_fields.items():
                    change_type = _EMPLOYMENT_CHANGE_TYPE_MAP.get(
                        field, field.upper(),
                    )
                    _create_employment_change(
                        db=db, employment_id=employment.id,
                        change_type=change_type,
                        before_value=change["before"],
                        after_value=change["after"],
                        operator=operator,
                    )
                    setattr(employment, field, change["after"])
                employment.updated_by = operator_id
                db.flush()

    # ── 4. 入职日期变更 ──
    if employment and "hire_date" in diff:
        old_date = _parse_optional_date(data.get("hire_date_old") or getattr(employment, "hire_date", None))
        new_date = _parse_optional_date(data.get("hire_date"))
        if new_date and not _values_equal(new_date, old_date):
            _create_hr_confirmation(
                db=db, employee_id=employee_id,
                employment_id=employment.id,
                issue_code=ConfirmationIssueCode.ACTUAL_HIRE_DATE_CHANGE,
                title="实际入职日期变更",
                description=f"入职日期从 {old_date} 变更为 {new_date}",
                before=old_date, after=new_date,
                import_batch_id=batch_id, import_row_id=row.id,
            )
            confirmations_created += 1

    # ── 5. 财务账号：APPEND_RECORD 模式 —— 不创建记录，仅创建确认事项 ──
    for acct in _extract_account_data(data):
        # 检查是否已存在相同卡号
        existing = _find_account_by_number(
            db, employee_id, acct["account_type"].value, acct["account_no"],
        )
        if existing:
            # 已存在相同账号，无变化
            continue

        # 不立即创建账号，生成 HR 确认事项
        _create_hr_confirmation(
            db=db, employee_id=employee_id,
            employment_id=employment.id if employment else None,
            issue_code=(
                ConfirmationIssueCode.NEW_BANK_ACCOUNT
                if acct["account_type"] == AccountType.BANK
                else ConfirmationIssueCode.NEW_ALIPAY_ACCOUNT
            ),
            title=f"新增{'银行卡' if acct['account_type'] == AccountType.BANK else '支付宝'}账号",
            description=f"新增 {acct['account_type'].value} 账号: {acct['account_no']}",
            before=None, after=acct,
            import_batch_id=batch_id, import_row_id=row.id,
        )
        confirmations_created += 1

    # ── 6. 合同信息变更（确认字段 —— 不修改，仅创建确认项）──
    contract_data = _extract_contract_data(data)
    if contract_data and diff.keys() & contract_data.keys():
        # 检查合同字段是否有实际变化
        has_contract_change = False
        for k in contract_data:
            if k in diff:
                has_contract_change = True
                break

        if has_contract_change:
            _create_hr_confirmation(
                db=db, employee_id=employee_id,
                employment_id=employment.id if employment else None,
                issue_code=ConfirmationIssueCode.CONTRACT_CHANGE,
                title="合同信息变更",
                description=f"合同信息变更: {json.dumps(contract_data, ensure_ascii=False)}",
                before=None, after=contract_data,
                import_batch_id=batch_id, import_row_id=row.id,
            )
            confirmations_created += 1

    # ── 7. 薪资变更（自动创建薪酬记录）──
    salary_data = _extract_salary_data(data)
    if salary_data:
        comp = CompensationRecord(
            employee_id=employee_id,
            employment_id=employment.id if employment else None,
            **salary_data,
            source_type=AttributeSource.ROSTER_IMPORT,
            import_batch_id=batch_id,
            effective_date=date.today(),
        )
        db.add(comp)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_COMPENSATION",
            target_table="compensation_record",
            target_id=comp.id, before=None, after=comp.dict(),
            reversible=True,
        )

    # ── 8. 备注去重追加（幂等键：import_batch_id + import_row_id + content_hash）──
    _create_note_if_needed(
        db, data, employee_id,
        employment.id if employment else None,
        batch_id, row.id, row.row_no,
    )

    # ── 更新行状态 ──
    row.row_status = RosterRowStatus.IMPORTED
    row.execution_status = ExecutionStatus.IMPORTED
    if confirmations_created > 0:
        row.review_status = "PENDING"
    else:
        row.review_status = "CLEAN"
    db.flush()

    return {
        "employee_id": employee_id,
        "action": "updated",
        "confirmations_created": confirmations_created,
    }


def _process_skip_row(
    db: DBSession,
    row: RosterImportRow,
    operator: dict,
) -> None:
    """处理跳过的行 —— 仅标记状态，不做任何业务操作。"""
    row.row_status = RosterRowStatus.SKIPPED
    row.execution_status = ExecutionStatus.SKIPPED
    row.review_status = "IGNORED"
    db.flush()


def _parse_planned_action(row: RosterImportRow) -> dict:
    """解析行的 planned_actions_json。"""
    if not row.planned_actions_json:
        return {}
    try:
        return json.loads(row.planned_actions_json) or {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ============================================================
# 内部辅助函数
# ============================================================


# ============================================================
# 生命周期评估集成
# ============================================================


def _get_lifecycle_decision(
    row: RosterImportRow,
    data: dict,
    mode: RosterImportMode | str,
) -> dict:
    """获取生命周期评估结果。

    优先使用预览时保存的 lifecycle_decision_json，
    没有时（如跳过预览阶段）则重新评估。
    """
    if row.lifecycle_decision_json:
        try:
            return json.loads(row.lifecycle_decision_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # 重新评估
    mode_str = _enum_value(mode) if mode else None
    result = evaluate_roster_lifecycle(data, mode_str)
    row.lifecycle_decision_json = json.dumps(result, ensure_ascii=False, default=str)
    return result


def _create_lifecycle_confirmations(
    db: DBSession,
    employee_id: int,
    employment_id: int | None,
    lifecycle_issues: list[dict],
    batch_id: int,
    row_id: int,
) -> int:
    """根据生命周期评估中的问题创建 HR 确认事项。

    Returns:
        创建的确认事项数量。
    """
    count = 0
    for iss in lifecycle_issues:
        issue_code = iss.get("issue_code", "")
        # 只有特定代码需要创建确认事项
        if issue_code in ("MISSING_REGULARIZATION_DATE", "EMPLOYMENT_FORM_REGULARIZATION_CONFLICT"):
            _create_hr_confirmation(
                db=db,
                employee_id=employee_id,
                employment_id=employment_id,
                issue_code=issue_code,
                title=iss.get("title", ""),
                description=iss.get("message"),
                before=iss.get("old_value"),
                after=iss.get("new_value"),
                import_batch_id=batch_id,
                import_row_id=row_id,
            )
            count += 1
    return count


def _determine_regularized_status(data: dict, mode: RosterImportMode) -> bool:
    """判断员工是否应初始化为已转正（备用函数，优先使用生命周期评估器）。

    严格规则（P0）：
    1. Excel 写"正式" → 是。
    2. Excel 存在不晚于今天的实际转正日期 → 是。
    3. 仅根据预计转正日期过去 → 否（绝不自动转正）。
    4. 仅根据试用期计算到期 → 否（绝不自动转正）。
    """
    # 用工形式检查
    raw_form = str(data.get("employment_type") or "").strip().lower()
    if raw_form == "正式":
        return True

    # 明确标记已转正
    if data.get("probation_status") == "REGULARIZED":
        return True
    if data.get("regularized") is True:
        return True

    # 存在不晚于今天的实际转正日期
    reg_date = data.get("regularization_date")
    if reg_date is not None:
        if isinstance(reg_date, date):
            return reg_date <= date.today()
        return True  # 有转正日期就视为已转正

    return False


def _determine_employment_status(
    mode: RosterImportMode,
    hire_date: date,
    today: date,
    is_regularized: bool,
) -> tuple[EmploymentStatus, ProbationStatus]:
    """根据模式决定在职状态和试用期状态。

    规则（P0）：
    - INITIALIZE 模式且在职且日期不晚于今天 → ACTIVE
    - 否则一律 PENDING（不得自动入职）
    """
    if _enum_value(mode) == RosterImportMode.INITIALIZE.value:
        if hire_date <= today:
            emp_status = EmploymentStatus.ACTIVE
            prob_status = (
                ProbationStatus.REGULARIZED
                if is_regularized
                else ProbationStatus.IN_PROGRESS
            )
        else:
            emp_status = EmploymentStatus.PENDING
            prob_status = ProbationStatus.NOT_STARTED
    else:
        # SYNC 模式：一律 PENDING，绝不自动激活
        emp_status = EmploymentStatus.PENDING
        prob_status = (
            ProbationStatus.REGULARIZED
            if is_regularized
            else ProbationStatus.NOT_STARTED
        )

    return emp_status, prob_status


def _validate_probation_months(data: dict, is_regularized: bool) -> int:
    """验证并返回试用期月数。

    规则（P0）：
    - 有效范围：1～6
    - 0、负数、7及以上、非数字 → 阻断
    - 空白时：试用员工默认3个月，已转正员工不计算
    """
    raw = data.get("probation_months")
    if raw is None:
        return 3 if not is_regularized else 0  # 已转正不计算试用期

    try:
        pm = int(raw)
    except (ValueError, TypeError):
        raise ValidationError(f"试用期月数「{raw}」无法解析为有效整数")

    if pm < 0:
        raise ValidationError(f"试用期月数不能为负数: {pm}")
    if pm == 0:
        if is_regularized:
            return 0
        raise ValidationError("试用期月数为 0，但员工未标记为已转正")
    if pm > 6:
        raise ValidationError(
            f"试用期月数 {pm} 超过最大允许值 6 个月"
        )

    return pm


def _set_profile_incomplete(db: DBSession, employee_id: int) -> None:
    """标记员工资料为不完整。"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee:
        employee.profile_completeness_status = ProfileCompleteness.INCOMPLETE
        db.flush()


def _find_account_by_number(
    db: DBSession,
    employee_id: int,
    account_type: str,
    account_no: str,
) -> EmployeeFinancialAccount | None:
    """按 employee_id + account_type + account_no 查找已有账号。"""
    return (
        db.query(EmployeeFinancialAccount)
        .filter(
            EmployeeFinancialAccount.employee_id == employee_id,
            EmployeeFinancialAccount.account_type == account_type,
            EmployeeFinancialAccount.account_no == account_no,
            EmployeeFinancialAccount.is_deleted == False,
        )
        .first()
    )


def _create_field_confirmation(
    db: DBSession,
    employee_id: int,
    employment_id: int | None,
    field: str,
    old_val: Any,
    new_val: Any,
    batch_id: int,
    row_id: int,
) -> HrConfirmationItem:
    """为字段变更创建 HR 确认事项。

    确认字段在提交时绝不修改业务数据，只创建确认事项。
    """
    policy = get_field_policy(field)
    issue_code = policy.confirmation_issue_code if policy else f"FIELD_CHANGE_{field.upper()}"
    field_label = policy.labels[0] if (policy and policy.labels) else field

    return _create_hr_confirmation(
        db=db, employee_id=employee_id, employment_id=employment_id,
        issue_code=issue_code,
        title=f"员工{field_label}变更",
        description=f"{field_label}由「{old_val}」变更为「{new_val}」，请确认是否更新。",
        before={field: old_val} if old_val is not None else None,
        after={field: new_val} if new_val is not None else None,
        import_batch_id=batch_id, import_row_id=row_id,
    )


def _create_note_if_needed(
    db: DBSession,
    data: dict,
    employee_id: int,
    employment_id: int | None,
    batch_id: int,
    row_id: int,
    row_no: int,
) -> None:
    """仅在必要时创建备注（幂等键：import_batch_id + import_row_id + content_hash）。"""
    remark = data.get("remark") or data.get("remarks")
    if not remark:
        return

    content_hash = _compute_content_hash(str(remark))
    idempotent_key = f"{batch_id}_{row_id}_{content_hash}"

    # 同批次同行的相同备注不重复创建
    existing_note = (
        db.query(EmployeeNote)
        .filter(
            EmployeeNote.employee_id == employee_id,
            EmployeeNote.source_type == AttributeSource.ROSTER_IMPORT.value,
            EmployeeNote.import_batch_id == batch_id,
            EmployeeNote.source_row_no == row_no,
            EmployeeNote.content_hash == content_hash,
        )
        .first()
    )
    if existing_note:
        return

    note = EmployeeNote(
        employee_id=employee_id,
        employment_id=employment_id,
        content=str(remark),
        source_type=AttributeSource.ROSTER_IMPORT,
        source_id=str(batch_id),
        import_batch_id=batch_id,
        source_row_no=row_no,
        content_hash=content_hash,
    )
    db.add(note)
    db.flush()

    _write_operation(
        db=db, batch_id=batch_id, row_id=row_id,
        employee_id=employee_id, operation_type="CREATE_NOTE",
        target_table="employee_note", target_id=note.id,
        before=None, after=note.dict(), reversible=True,
    )


def _create_profile(
    db: DBSession,
    employee_id: int,
    data: dict,
    operator: dict,
) -> EmployeeProfile:
    """创建员工档案。"""
    profile = EmployeeProfile(
        employee_id=employee_id,
        identity_card=data.get("identity_card"),
        gender=data.get("gender"),
        birth_date=data.get("birth_date"),
        household_registration=data.get("household_registration"),
        residence_address=data.get("residence_address"),
        household_type=data.get("household_type"),
        graduation_school=data.get("graduation_school"),
        major=data.get("major"),
        education_level=data.get("education_level"),
        social_insurance_status=data.get("social_insurance_status"),
        housing_fund_status=data.get("housing_fund_status"),
        social_insurance_policy=data.get("social_insurance_policy"),
        housing_fund_policy=data.get("housing_fund_policy"),
        social_insurance_start_date=_parse_optional_date(data.get("social_insurance_start_date")),
        housing_fund_start_date=_parse_optional_date(data.get("housing_fund_start_date")),
        benefit_raw_text=data.get("benefit_raw_text"),
        created_by=operator.get("user_id", "system"),
    )
    db.add(profile)
    db.flush()
    return profile


def _create_attribute_history(
    db: DBSession,
    employee_id: int,
    employment_id: int | None,
    field_name: str,
    before: Any,
    after: Any,
    source: AttributeSource,
    batch_id: int,
    operator: dict,
) -> None:
    """记录员工属性变更历史。"""
    history = EmployeeAttributeHistory(
        employee_id=employee_id,
        employment_id=employment_id,
        category=(
            "BENEFIT"
            if field_name.removeprefix("profile.") in BENEFIT_PROFILE_FIELDS
            else None
        ),
        field_name=field_name,
        before_value_json=(
            json.dumps(before, ensure_ascii=False, default=str)
            if before is not None else None
        ),
        after_value_json=(
            json.dumps(after, ensure_ascii=False, default=str)
            if after is not None else None
        ),
        effective_date=date.today(),
        source_type=source,
        source_id=str(batch_id),
        import_batch_id=batch_id,
        operator_name=operator.get("user_id", "system"),
        created_by=operator.get("user_id", "system"),
    )
    db.add(history)
    db.flush()


def _create_employment_change(
    db: DBSession,
    employment_id: int,
    change_type: str,
    before_value: Any,
    after_value: Any,
    operator: dict,
) -> dict:
    """创建任职变更记录。"""
    change = EmploymentChange(
        employment_id=employment_id,
        change_type=change_type,
        effective_date=date.today(),
        before_data=(
            json.dumps(before_value, ensure_ascii=False, default=str)
            if before_value is not None else None
        ),
        after_data=(
            json.dumps(after_value, ensure_ascii=False, default=str)
            if after_value is not None else None
        ),
        confirmed_by=operator.get("user_id", "system"),
        confirmed_at=datetime.now(),
        created_by=operator.get("user_id", "system"),
    )
    db.add(change)
    db.flush()
    return change.dict()


def _generate_initialization_tasks(
    db: DBSession,
    employment_id: int,
    actual_hire_date: date,
) -> None:
    """INITIALIZE 模式下生成跟进任务（仅生成未来日期的节点，跳过已过期节点）。"""
    today = date.today()

    nodes = (
        db.query(FollowupNodeDefinition)
        .filter(
            FollowupNodeDefinition.enabled == True,
            FollowupNodeDefinition.is_deleted == False,
        )
        .all()
    )

    for node in nodes:
        trigger_type = _enum_value(node.trigger_type)
        if trigger_type == "MANUAL":
            continue

        offset = node.offset_days or 0
        planned_date = actual_hire_date + timedelta(days=offset)

        if planned_date < today:
            continue

        idempotency_key = f"auto_task_{employment_id}_{node.node_code}"

        existing = (
            db.query(FollowupTask)
            .filter(FollowupTask.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            continue

        task = FollowupTask(
            employment_id=employment_id,
            node_definition_id=node.id,
            node_version=node.node_version,
            node_code_snapshot=node.node_code,
            task_name=node.node_name,
            task_source="AUTO",
            trigger_type_snapshot=trigger_type,
            offset_days_snapshot=node.offset_days,
            planned_date=planned_date,
            original_planned_date=planned_date,
            date_adjusted_manually=False,
            followup_status="PENDING",
            confirmation_mode=_enum_value(node.confirmation_mode),
            idempotency_key=idempotency_key,
        )
        db.add(task)

    db.flush()


def _create_hr_confirmation(
    db: DBSession,
    employee_id: int,
    employment_id: int | None,
    issue_code: ConfirmationIssueCode | str,
    title: str,
    description: str | None,
    before: Any,
    after: Any,
    import_batch_id: int | None = None,
    import_row_id: int | None = None,
) -> HrConfirmationItem:
    """创建 HR 确认项。

    确保保存 import_batch_id 和 import_row_id 以追踪来源。
    相同 import_batch_id + import_row_id + issue_code 的创建幂等。
    """
    # 幂等检查
    if import_batch_id and import_row_id:
        existing = (
            db.query(HrConfirmationItem)
            .filter(
                HrConfirmationItem.import_batch_id == import_batch_id,
                HrConfirmationItem.import_row_id == import_row_id,
                HrConfirmationItem.issue_code == _enum_value(issue_code),
            )
            .first()
        )
        if existing:
            return existing

    item = HrConfirmationItem(
        employee_id=employee_id,
        employment_id=employment_id,
        source_type="ROSTER_IMPORT",
        source_id=str(import_batch_id) if import_batch_id else None,
        issue_code=_enum_value(issue_code),
        title=title,
        description=description,
        before_data_json=(
            json.dumps(before, ensure_ascii=False, default=str)
            if before is not None else None
        ),
        after_data_json=(
            json.dumps(after, ensure_ascii=False, default=str)
            if after is not None else None
        ),
        import_batch_id=import_batch_id,
        import_row_id=import_row_id,
        item_status="PENDING",
    )
    db.add(item)
    db.flush()

    # 同步记录操作日志
    _write_operation(
        db=db, batch_id=import_batch_id or 0, row_id=import_row_id or 0,
        employee_id=employee_id,
        operation_type="CREATE_CONFIRMATION",
        target_table="hr_confirmation_item",
        target_id=item.id,
        before=None,
        after={"title": title, "issue_code": _enum_value(issue_code)},
        reversible=True,
    )

    return item


def _write_operation(
    db: DBSession,
    batch_id: int,
    row_id: int,
    employee_id: int,
    operation_type: str,
    target_table: str,
    target_id: int | None,
    before: Any,
    after: Any,
    reversible: bool = True,
) -> RosterImportOperation:
    """记录导入操作。"""
    op = RosterImportOperation(
        batch_id=batch_id,
        row_id=row_id,
        employee_id=employee_id,
        operation_type=operation_type,
        target_table=target_table,
        target_id=target_id,
        before_snapshot_json=(
            json.dumps(before, ensure_ascii=False, default=str)
            if before is not None else None
        ),
        after_snapshot_json=(
            json.dumps(after, ensure_ascii=False, default=str)
            if after is not None else None
        ),
        reversible=reversible,
    )
    db.add(op)
    db.flush()
    return op


# ============================================================
# 内部数据提取工具
# ============================================================


def _get_batch_or_error(
    db: DBSession,
    batch_id: int,
) -> RosterImportBatch:
    """查询批次，不存在时抛异常。"""
    batch = db.query(RosterImportBatch).filter(
        RosterImportBatch.id == batch_id,
    ).first()
    if not batch:
        raise ResourceNotFound(f"导入批次不存在: {batch_id}")
    return batch


def _load_processable_rows(
    db: DBSession,
    batch_id: int,
) -> list[RosterImportRow]:
    """加载可处理的行（排除已导入、错误、跳过、未变更的行）。"""
    excluded = [
        RosterRowStatus.ERROR.value,
        RosterRowStatus.SKIPPED.value,
        RosterRowStatus.UNCHANGED.value,
        RosterRowStatus.IMPORTED.value,
    ]
    return (
        db.query(RosterImportRow)
        .filter(
            RosterImportRow.batch_id == batch_id,
            ~RosterImportRow.row_status.in_(excluded),
        )
        .order_by(RosterImportRow.row_no.asc())
        .all()
    )


def _resolve_employee_id(
    row: RosterImportRow,
    cache: dict[int, Employee],
) -> int:
    """解析员工 ID。"""
    if row.employee_id:
        return row.employee_id
    raise ValidationError(
        f"行 {row.row_no} 状态为更新但缺少 employee_id"
    )


def _parse_row_data(row: RosterImportRow) -> dict:
    """解析行的标准化数据 JSON。"""
    if not row.normalized_data_json:
        return {}
    try:
        return json.loads(row.normalized_data_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_diff(row: RosterImportRow) -> dict:
    """解析行的差异数据 JSON。"""
    if not row.diff_json:
        return {}
    try:
        diff = json.loads(row.diff_json)
        if isinstance(diff, dict):
            return diff
        if isinstance(diff, list):
            return {item.get("field", str(i)): item for i, item in enumerate(diff)}
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_profile_data(data: dict) -> dict:
    """从行数据中提取 profile 字段。"""
    result = {}
    for k, v in data.items():
        if k not in _PROFILE_AUTO_FIELDS:
            continue
        if v is None and k not in _BENEFIT_CLEARABLE_FIELDS:
            continue
        if k in {"birth_date", "social_insurance_start_date", "housing_fund_start_date"}:
            result[k] = _parse_optional_date(v)
        else:
            result[k] = v
    return result


def _parse_optional_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def _extract_contract_data(data: dict) -> dict:
    """从行数据中提取合同字段。"""
    contract_keys = {
        "contract_type", "signing_company", "start_date",
        "end_date", "contract_status", "contract_end_date",
    }
    result = {
        k: v for k, v in data.items()
        if k in contract_keys and v is not None
    }
    for date_field in ("start_date", "end_date", "contract_end_date"):
        if date_field in result:
            result[date_field] = _parse_optional_date(result[date_field])
    return result


def _extract_account_data(data: dict) -> list[dict]:
    """从行数据中提取财务账号信息。"""
    accounts: list[dict] = []
    bank_account = data.get("bank_account") or data.get("bank_card_no") or data.get("bank_card")
    if bank_account:
        accounts.append({
            "account_type": AccountType.BANK,
            "account_no": str(bank_account),
            "bank_name": data.get("bank_name"),
        })
    alipay_account = data.get("alipay_account") or data.get("alipay")
    if alipay_account:
        accounts.append({
            "account_type": AccountType.ALIPAY,
            "account_no": str(alipay_account),
            "bank_name": None,
        })
    return accounts


def _extract_salary_data(data: dict) -> dict:
    """从行数据中提取薪资信息，返回 CompensationRecord 字段。"""
    salary_text = data.get("salary_text") or data.get("salary")
    if not salary_text:
        return {}

    parsed = parse_salary_text(str(salary_text))

    comp_fields = {
        "raw_salary_text", "salary_type", "base_salary",
        "probation_salary", "regular_salary", "daily_rate",
        "performance_amount", "performance_ratio",
        "commission_text", "other_text",
    }

    result: dict = {}
    for k, v in parsed.items():
        if k in comp_fields and v is not None:
            if isinstance(v, (int, float)) and not isinstance(v, Decimal):
                result[k] = Decimal(str(v))
            else:
                result[k] = v

    return result


def _extract_assessment_data(data: dict) -> list[dict]:
    """从行数据中提取测评信息。"""
    assessments: list[dict] = []
    mbti = data.get("mbti")
    if mbti:
        assessments.append({
            "assessment_type": AssessmentType.MBTI,
            "result_text": str(mbti),
        })
    pdp = data.get("pdp")
    if pdp:
        assessments.append({
            "assessment_type": AssessmentType.PDP,
            "result_text": str(pdp),
        })
    return assessments


def _find_current_employment(
    db: DBSession,
    employee_id: int,
) -> EmploymentRecord | None:
    """找到员工的当前有效任职。"""
    return (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.desc())
        .first()
    )


def _compute_content_hash(content: str) -> str:
    """计算备注内容的 SHA-256 哈希值。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _values_equal(a: Any, b: Any) -> bool:
    """比较两个值是否在语义上相等。"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, (date, datetime)) and isinstance(b, (date, datetime)):
        return str(a) == str(b)
    return str(a) == str(b)

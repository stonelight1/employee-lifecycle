"""花名册导入提交服务 —— 执行实际业务数据写入。

注意：所有业务写入必须在单个数据库事务中完成。
任何失败都必须引发异常，由调用方负责回滚事务和更新批次状态。
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
    ContractType,
    EmployeeStatus,
    EmploymentStatus,
    EmploymentType,
    IssueSeverity,
    ProbationStatus,
    RosterBatchStatus,
    RosterImportMode,
    RosterRowStatus,
    SalaryType,
    WorkMode,
)
from ..exceptions import (
    Conflict,
    DuplicateRequest,
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

from .salary_parser import parse_salary_text
from .benefit_parser import BENEFIT_PROFILE_FIELDS

# ============================================================
# 常量定义 —— 移至 roster_preview_service 共享
# ============================================================

# 自动更新字段 —— 无需 HR 确认即可直接应用
AUTO_UPDATE_FIELDS: set[str] = {
    "mobile",
    "email",
    "source",
    "gender",
    "education_level",
    "graduation_school",
    "major",
}

# 需 HR 确认的字段 —— 变更时生成确认项等待人工处理
CONFIRMATION_FIELDS: set[str] = {
    "identity_card",
    "birth_date",
    "household_registration",
    "residence_address",
    "household_type",
    "social_insurance_status",
    "housing_fund_status",
    "employee_no",
    "name",
    "bank_account",
    "alipay_account",
    "contract_type",
    "signing_company",
    "start_date",
    "end_date",
    "salary_text",
}

# Employee 表可更新字段
_EMPLOYEE_UPDATE_FIELDS: set[str] = {
    "employee_no",
    "mobile",
    "email",
    "source",
}

# EmploymentRecord 表可更新字段
_EMPLOYMENT_UPDATE_FIELDS: set[str] = {
    "department",
    "position",
    "manager_name",
    "team_name",
    "employment_type",
    "work_city",
    "work_mode",
}

# EmployeeProfile 表可更新字段
_PROFILE_UPDATE_FIELDS: set[str] = {
    "identity_card",
    "gender",
    "birth_date",
    "household_registration",
    "residence_address",
    "household_type",
    "graduation_school",
    "major",
    "education_level",
    "social_insurance_status",
    "housing_fund_status",
    "social_insurance_policy",
    "housing_fund_policy",
    "social_insurance_start_date",
    "housing_fund_start_date",
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
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "confirmation": 0,
    }

    try:
        for row in rows:
            if _enum_value(row.row_status) == RosterRowStatus.SKIPPED.value:
                _process_skip_row(db, row, operator)
                summary["skipped"] += 1
                continue

            if _enum_value(row.row_status) == RosterRowStatus.NEW.value:
                result = _process_new_row(
                    db, row, batch_id, batch.mode, operator,
                )
                summary["created"] += 1

            elif _enum_value(row.row_status) in (
                RosterRowStatus.UPDATE.value,
                RosterRowStatus.NEEDS_CONFIRMATION.value,
            ):
                employee_id = _resolve_employee_id(row, employee_cache)
                result = _process_update_row(
                    db, row, employee_id, batch_id, batch.mode, operator,
                )
                summary["updated"] += 1
                if result.get("confirmations_created", 0) > 0:
                    summary["confirmation"] += result["confirmations_created"]

        # 更新批次为成功
        now = datetime.now()
        batch.batch_status = RosterBatchStatus.SUCCEEDED
        batch.completed_at = now
        batch.imported_count = summary["created"] + summary["updated"]
        batch.skipped_count = summary["skipped"]
        db.flush()

    except Exception as e:
        # 失败时记录状态，由调用方负责事务回滚
        now = datetime.now()
        batch.batch_status = RosterBatchStatus.FAILED
        batch.failed_at = now
        batch.failure_message = str(e)
        db.flush()
        raise

    # 操作日志
    operation_log_service.create_log(
        db=db,
        operator_id=operator.get("user_id", "system"),
        object_type="ROSTER_IMPORT",
        object_id=str(batch_id),
        operation_type="COMMIT",
        after_data={
            "batch_no": batch.batch_no,
            "summary": summary,
        },
        business_id=batch_id,
    )

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "status": _enum_value(batch.batch_status),
        "message": "导入已完成",
        "summary": summary,
    }


# ============================================================
# 行处理
# ============================================================


def _process_new_row(
    db: DBSession,
    row: RosterImportRow,
    batch_id: int,
    mode: RosterImportMode,
    operator: dict,
) -> dict:
    """处理新增行 —— 创建员工、任职、档案及相关关联记录。"""
    data = _parse_row_data(row)

    if not data.get("name"):
        raise ValidationError(f"行 {row.row_no} 缺少员工姓名")

    today = date.today()

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
    if profile_data:
        _create_profile(db, employee_id, profile_data, operator)
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_PROFILE", target_table="employee_profile",
            target_id=employee_id, before=None, after=profile_data, reversible=True,
        )

    # ── 3. 创建 EmploymentRecord ──
    hire_date = data.get("hire_date")
    if not hire_date:
        raise ValidationError(f"行 {row.row_no} 缺少入职日期 (hire_date)")

    if not isinstance(hire_date, date):
        try:
            hire_date = date.fromisoformat(str(hire_date))
        except (ValueError, TypeError):
            raise ValidationError(f"行 {row.row_no} 入职日期格式无效: {hire_date}")

    is_regularized = (
        data.get("probation_status") == "REGULARIZED"
        or data.get("regularized") is True
    )

    # 自动判断转正状态
    # 如果导入数据提供了转正日期(regularization_date)，或试用期结束日期已过，则视为已转正
    if not is_regularized:
        if data.get("regularization_date") is not None:
            is_regularized = True
        else:
            prob_months = data.get("probation_months", 3)
            if not isinstance(prob_months, int) or prob_months < 1:
                prob_months = 3
            calc_end = calculate_probation_end_date(hire_date, prob_months)
            if calc_end < today:
                is_regularized = True

    if _enum_value(mode) == RosterImportMode.INITIALIZE.value:
        # INITIALIZE 模式：入职即激活，按实际入职日期计算试用期
        emp_status = EmploymentStatus.ACTIVE
        prob_status = (
            ProbationStatus.REGULARIZED
            if is_regularized
            else ProbationStatus.IN_PROGRESS
        )
    else:
        # SYNC 模式：按日期决定 pending / active
        emp_status = (
            EmploymentStatus.ACTIVE if hire_date <= today
            else EmploymentStatus.PENDING
        )
        prob_status = (
            ProbationStatus.REGULARIZED
            if is_regularized
            else (
                ProbationStatus.IN_PROGRESS if hire_date <= today
                else ProbationStatus.NOT_STARTED
            )
        )

    # 设置试用期起止日期（已转正员工同样保留历史试用期日期）
    prob_months = data.get("probation_months", 3)
    if not isinstance(prob_months, int) or prob_months < 1:
        prob_months = 3
    probation_end = None
    probation_start = None
    if prob_status in (ProbationStatus.IN_PROGRESS, ProbationStatus.REGULARIZED):
        probation_end = calculate_probation_end_date(hire_date, prob_months)
        probation_start = hire_date

    # 检查是否已有有效任职（防止重复创建）
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
        # 复用了已有任职，更新其字段
        employment = existing_active
        for field in _EMPLOYMENT_UPDATE_FIELDS:
            if field in data:
                setattr(employment, field, data[field])
        employment.updated_by = operator.get("user_id", "system")
        db.flush()
    else:
        # 确定 employment_seq
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
            employment_status=emp_status,
            hire_date=hire_date,
            actual_hire_date=hire_date if hire_date <= today else None,
            probation_start_date=probation_start,
            probation_end_date=probation_end,
            probation_status=prob_status,
            probation_months=prob_months,
            department=data.get("department"),
            position=data.get("position"),
            manager_name=data.get("manager_name"),
            team_name=data.get("team_name"),
            employment_type=data.get("employment_type", EmploymentType.FORMAL),
            work_city=data.get("work_city"),
            work_mode=data.get("work_mode", WorkMode.UNKNOWN),
            date_rule_source="AUTO",
            probation_end_date_source="AUTO",
            created_by=operator.get("user_id", "system"),
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

    # ── 4. INITIALIZE 模式生成跟进任务（仅未来节点）──
    if _enum_value(mode) == RosterImportMode.INITIALIZE.value and not is_regularized:
        _generate_initialization_tasks(db, employment_id, hire_date)

    # ── 5. 创建 Contract ──
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
            created_by=operator.get("user_id", "system"),
        )
        db.add(contract)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_CONTRACT", target_table="employment_contract",
            target_id=contract.id, before=None, after=contract.dict(),
            reversible=True,
        )

    # ── 6. 创建 FinancialAccount ──
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
            created_by=operator.get("user_id", "system"),
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

    # ── 7. 创建 Compensation ──
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

    # ── 8. 创建 Assessment ──
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

    # ── 9. 创建 Note ──
    remark = data.get("remark") or data.get("remarks")
    if remark:
        note = EmployeeNote(
            employee_id=employee_id,
            employment_id=employment_id,
            content=str(remark),
            source_type=AttributeSource.ROSTER_IMPORT,
            source_id=str(batch_id),
            import_batch_id=batch_id,
            source_row_no=row.row_no,
            content_hash=_compute_content_hash(str(remark)),
        )
        db.add(note)
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_NOTE",
            target_table="employee_note",
            target_id=note.id, before=None, after=note.dict(),
            reversible=True,
        )

    # ── 10. 更新行状态 ──
    row.employee_id = employee_id
    row.row_status = RosterRowStatus.IMPORTED
    db.flush()

    return {
        "employee_id": employee_id,
        "employment_id": employment_id,
        "action": "created",
    }


def _process_update_row(
    db: DBSession,
    row: RosterImportRow,
    employee_id: int,
    batch_id: int,
    mode: RosterImportMode,
    operator: dict,
) -> dict:
    """处理更新行 —— 更新已有员工信息。

    SYNC 模式：创建 EmploymentChange 记录以追踪历史。
    INITIALIZE 模式：直接更新当前值，不创建变更历史（花名册本身就是"初始化"）。
    """
    data = _parse_row_data(row)
    diff = _parse_diff(row)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or employee.is_deleted:
        raise ResourceNotFound(f"待更新员工 {employee_id} 不存在或已删除")

    employment = _find_current_employment(db, employee_id)
    confirmations_created = 0

    # ── 1. 更新 Employee 字段 ──
    emp_before: dict[str, Any] = {}
    emp_updates: dict[str, Any] = {}
    for field in _EMPLOYEE_UPDATE_FIELDS:
        if field not in data or field not in diff:
            continue
        old_val = getattr(employee, field, None)
        new_val = data[field]
        if new_val is not None and new_val != old_val:
            emp_before[field] = old_val
            emp_updates[field] = new_val
            setattr(employee, field, new_val)

            _create_attribute_history(
                db=db, employee_id=employee_id, employment_id=None,
                field_name=field, before=old_val, after=new_val,
                source=AttributeSource.ROSTER_IMPORT, batch_id=batch_id,
                operator=operator,
            )

            if field in CONFIRMATION_FIELDS and field != "mobile":
                _create_hr_confirmation(
                    db=db, employee_id=employee_id, employment_id=None,
                    issue_code=f"FIELD_CHANGE_{field.upper()}",
                    title=f"员工 {field} 变更",
                    description=f"字段 {field} 由 '{old_val}' 变更为 '{new_val}'",
                    before=old_val, after=new_val,
                )
                confirmations_created += 1

    if emp_updates:
        employee.updated_by = operator.get("user_id", "system")
        db.flush()
        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="UPDATE_EMPLOYEE", target_table="employee",
            target_id=employee_id, before=emp_before, after=emp_updates,
            reversible=True,
        )

    # ── 2. 更新 Profile ──
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
            if value != old_val:
                profile_before[field] = old_val
                profile_updates[field] = value
                setattr(profile, field, value)

                _create_attribute_history(
                    db=db, employee_id=employee_id, employment_id=None,
                    field_name=f"profile.{field}", before=old_val, after=value,
                    source=AttributeSource.ROSTER_IMPORT, batch_id=batch_id,
                    operator=operator,
                )

                if field in CONFIRMATION_FIELDS:
                    _create_hr_confirmation(
                        db=db, employee_id=employee_id, employment_id=None,
                        issue_code=f"FIELD_CHANGE_{field.upper()}",
                        title=f"员工档案 {field} 变更",
                        description=f"档案字段 {field} 由 '{old_val}' 变更为 '{value}'",
                        before=old_val, after=value,
                    )
                    confirmations_created += 1

        if profile_updates:
            db.flush()
            _write_operation(
                db=db, batch_id=batch_id, row_id=row.id,
                employee_id=employee_id, operation_type="UPDATE_PROFILE",
                target_table="employee_profile", target_id=employee_id,
                before=profile_before, after=profile_updates,
                reversible=True,
            )

    # ── 3. 处理 Employment 变更 ──
    if employment:
        emp_change_fields: dict[str, dict[str, Any]] = {}
        for field in _EMPLOYMENT_UPDATE_FIELDS:
            if field not in data or field not in diff:
                continue
            old_val = getattr(employment, field, None)
            new_val = data[field]
            if new_val is not None and new_val != old_val:
                emp_change_fields[field] = {"before": old_val, "after": new_val}

        if emp_change_fields:
            if _enum_value(mode) == RosterImportMode.INITIALIZE.value:
                # INITIALIZE：直接更新，不创建变更记录
                for field, change in emp_change_fields.items():
                    setattr(employment, field, change["after"])
                employment.updated_by = operator.get("user_id", "system")
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
                # SYNC：创建 EmploymentChange 记录
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
                employment.updated_by = operator.get("user_id", "system")
                db.flush()

    # ── 4. 财务账号：新增不覆盖 ──
    for acct in _extract_account_data(data):
        existing = (
            db.query(EmployeeFinancialAccount)
            .filter(
                EmployeeFinancialAccount.employee_id == employee_id,
                EmployeeFinancialAccount.account_type == acct["account_type"],
                EmployeeFinancialAccount.is_deleted == False,
            )
            .first()
        )
        if existing:
            continue

        account = EmployeeFinancialAccount(
            employee_id=employee_id,
            account_type=acct["account_type"],
            account_no=acct["account_no"],
            bank_name=acct.get("bank_name"),
            is_primary=False,
            account_status=AccountStatus.ACTIVE,
            source_type=AttributeSource.ROSTER_IMPORT,
            created_by=operator.get("user_id", "system"),
        )
        db.add(account)
        db.flush()

        _create_hr_confirmation(
            db=db, employee_id=employee_id,
            employment_id=employment.id if employment else None,
            issue_code=f"NEW_{acct['account_type'].value}_ACCOUNT",
            title=f"新增{acct['account_type'].value}账号",
            description=f"新增 {acct['account_type'].value} 账号: {acct['account_no']}",
            before=None, after=acct,
        )
        confirmations_created += 1

        _write_operation(
            db=db, batch_id=batch_id, row_id=row.id, employee_id=employee_id,
            operation_type="CREATE_FINANCIAL_ACCOUNT",
            target_table="employee_financial_account",
            target_id=account.id, before=None, after=account.dict(),
            reversible=True,
        )

    # ── 5. 合同信息变更（生成确认项）──
    contract_data = _extract_contract_data(data)
    if contract_data and diff.keys() & contract_data.keys():
        _create_hr_confirmation(
            db=db, employee_id=employee_id,
            employment_id=employment.id if employment else None,
            issue_code="CONTRACT_INFO_CHANGE",
            title="合同信息变更",
            description=f"合同信息变更: {json.dumps(contract_data, ensure_ascii=False)}",
            before=None, after=contract_data,
        )
        confirmations_created += 1

    # ── 6. 薪资变更 ──
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

    # ── 7. 备注去重追加 ──
    remark = data.get("remark") or data.get("remarks")
    if remark:
        content_hash = _compute_content_hash(str(remark))
        existing_note = (
            db.query(EmployeeNote)
            .filter(
                EmployeeNote.employee_id == employee_id,
                EmployeeNote.content_hash == content_hash,
            )
            .first()
        )
        if not existing_note:
            note = EmployeeNote(
                employee_id=employee_id,
                employment_id=employment.id if employment else None,
                content=str(remark),
                source_type=AttributeSource.ROSTER_IMPORT,
                source_id=str(batch_id),
                import_batch_id=batch_id,
                source_row_no=row.row_no,
                content_hash=content_hash,
            )
            db.add(note)
            db.flush()
            _write_operation(
                db=db, batch_id=batch_id, row_id=row.id,
                employee_id=employee_id, operation_type="CREATE_NOTE",
                target_table="employee_note", target_id=note.id,
                before=None, after=note.dict(), reversible=True,
            )

    # ── 更新行状态 ──
    row.row_status = RosterRowStatus.IMPORTED
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
    db.flush()


# ============================================================
# 内部辅助函数
# ============================================================


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

        # 跳过已过期节点
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
    issue_code: str,
    title: str,
    description: str | None,
    before: Any,
    after: Any,
) -> HrConfirmationItem:
    """创建 HR 确认项。"""
    item = HrConfirmationItem(
        employee_id=employee_id,
        employment_id=employment_id,
        source_type="ROSTER_IMPORT",
        source_id=None,
        issue_code=issue_code,
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
        item_status="PENDING",
    )
    db.add(item)
    db.flush()
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
    """记录导入操作。

    默认所有操作可回滚 (reversible=True)。
    转正确认、已确认离职等不可逆操作应传入 reversible=False。
    """
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


def _generate_idempotency_key(
    batch_id: int,
    row_id: int,
    action_type: str,
    field_key: str,
) -> str:
    """生成操作的幂等键。"""
    return f"roster_{batch_id}_{row_id}_{action_type}_{field_key}"


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
    """解析员工 ID。优先使用缓存，不存在时查库。"""
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
    """解析行的差异数据 JSON（返回差异发生变化的字段名集合）。"""
    if not row.diff_json:
        return {}
    try:
        diff = json.loads(row.diff_json)
        if isinstance(diff, dict):
            return diff
        if isinstance(diff, list):
            # 兼容列表格式
            return {item.get("field", str(i)): item for i, item in enumerate(diff)}
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_profile_data(data: dict) -> dict:
    """从行数据中提取 profile 字段。"""
    result = {}
    for k, v in data.items():
        if k not in _PROFILE_UPDATE_FIELDS:
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
        "end_date", "contract_status",
    }
    result = {
        k: v for k, v in data.items()
        if k in contract_keys and v is not None
    }
    # 确保日期字段为 Python date 对象，而非字符串
    for date_field in ("start_date", "end_date"):
        if date_field in result:
            result[date_field] = _parse_optional_date(result[date_field])
    return result


def _extract_account_data(data: dict) -> list[dict]:
    """从行数据中提取财务账号信息。"""
    accounts: list[dict] = []
    bank_account = data.get("bank_account") or data.get("bank_card_no")
    if bank_account:
        accounts.append({
            "account_type": AccountType.BANK,
            "account_no": str(bank_account),
            "bank_name": data.get("bank_name"),
        })
    alipay_account = data.get("alipay_account")
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
    """找到员工的当前有效任职（按创建时间倒序取最新）。"""
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
    """计算备注内容的 SHA-256 哈希值用于去重。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value

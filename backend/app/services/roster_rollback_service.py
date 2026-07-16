"""花名册导入撤销服务。

核心原则：
1. 只要存在冲突 → 不执行任何撤销 → 返回冲突列表 → 批次保持原状态。
2. 撤销任意一项抛异常 → 整个撤销事务回滚 → 批次不标记为 ROLLED_BACK。
3. 只支持已明确注册的 operation_type。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    AttributeSource,
    ConfirmationItemStatus,
    EmployeeStatus,
    OperationObjectType,
    RosterBatchStatus,
)
from ..exceptions import (
    Conflict,
    InvalidStateTransition,
    ResourceNotFound,
    ValidationError,
)
from ..models import (
    CommunicationRecord,
    CompensationRecord,
    Employee,
    EmployeeAssessment,
    EmployeeAttributeHistory,
    EmployeeFinancialAccount,
    EmployeeNote,
    EmployeeProfile,
    EmploymentContract,
    EmploymentRecord,
    FollowupTask,
    HrConfirmationItem,
    ProbationReview,
    RegularizationRecord,
    RosterImportBatch,
    RosterImportOperation,
    RosterImportRow,
    SeparationRecord,
    SystemTodo,
)
from ..services import operation_log_service

# ---------------------------------------------------------------------------
# 系统字段 —— 冲突检查时跳过
# ---------------------------------------------------------------------------

_SYSTEM_FIELDS: set[str] = {
    "id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "version",
    "is_deleted",
    "deleted_at",
    "deleted_by",
}

# 表名 -> 模型映射
_TABLE_MODEL_MAP: dict[str, Any] = {
    "employee": Employee,
    "employment_record": EmploymentRecord,
    "employee_profile": EmployeeProfile,
    "employee_note": EmployeeNote,
    "hr_confirmation_item": HrConfirmationItem,
    "followup_task": FollowupTask,
    "communication_record": CommunicationRecord,
    "employee_financial_account": EmployeeFinancialAccount,
    "employment_contract": EmploymentContract,
    "compensation_record": CompensationRecord,
    "employee_assessment": EmployeeAssessment,
    "regularization_record": RegularizationRecord,
    "separation_record": SeparationRecord,
    "probation_review": ProbationReview,
    "system_todo": SystemTodo,
}


# ---------------------------------------------------------------------------
# 公共函数
# ---------------------------------------------------------------------------


def preview_rollback(db: DBSession, batch_id: int) -> dict[str, Any]:
    """预览指定批次的撤销结果。

    加载批次及其所有操作，逐条检查是否可逆、是否存在数据冲突，
    最终返回按员工分组的撤销预览信息。
    """
    batch = _load_batch(db, batch_id)
    if batch.batch_status not in (
        RosterBatchStatus.SUCCEEDED,
        RosterBatchStatus.ROLLBACK_PREVIEW,
    ):
        raise InvalidStateTransition(
            f"批次 {batch.batch_no} 当前状态为 {batch.batch_status.value}，"
            "仅 SUCCEEDED 状态的批次可以预览撤销"
        )

    ops = _load_operations(db, batch_id)
    conflicts = _check_conflicts(db, ops)
    conflict_map = {c["operation_id"]: c for c in conflicts}

    employee_items: dict[int, list[dict[str, Any]]] = {}
    irreversible_ops: list[str] = []
    conflict_messages: list[str] = []

    for op in ops:
        employee_name = _get_employee_name(db, op.employee_id)
        details = _build_operation_details(op)
        conflict_info = conflict_map.get(op.id)

        item: dict[str, Any] = {
            "operation_id": op.id,
            "employee_id": op.employee_id,
            "employee_name": employee_name,
            "action": op.operation_type,
            "target_table": op.target_table,
            "details": details,
            "reversible": op.reversible,
            "conflict": conflict_info is not None,
            "conflict_reason": conflict_info["reason"] if conflict_info else None,
        }

        employee_items.setdefault(op.employee_id or 0, []).append(item)

        if not op.reversible:
            irreversible_ops.append(
                f"[{op.operation_type}] {employee_name}: {details}"
                f"（原因：{op.irreversible_reason or '操作本身不可逆'}）"
            )

        if conflict_info:
            conflict_messages.append(
                f"[{op.operation_type}] {employee_name}: {conflict_info['reason']}"
            )

    can_rollback = len(conflict_messages) == 0

    grouped_items: list[dict[str, Any]] = []
    for emp_id in sorted(employee_items.keys(), key=lambda x: x or 0):
        grouped_items.extend(employee_items[emp_id])

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "can_rollback": can_rollback,
        "items": grouped_items,
        "irreversible_operations": irreversible_ops,
        "conflicts": conflict_messages,
    }


def execute_rollback(
    db: DBSession,
    batch_id: int,
    operator: dict[str, Any],
) -> dict[str, Any]:
    """执行指定批次的撤销操作。

    核心规则：
    1. 只要存在冲突 → 不执行任何撤销 → 返回冲突列表 → 批次保持原状态。
    2. 撤销任意一项抛异常 → 整个撤销事务回滚 → 批次不标记为 ROLLED_BACK。
    3. 所有操作在同一个数据库事务中完成。
    """
    batch = _load_batch(db, batch_id)
    if batch.batch_status not in (
        RosterBatchStatus.SUCCEEDED,
        RosterBatchStatus.ROLLBACK_PREVIEW,
    ):
        raise InvalidStateTransition(
            f"批次 {batch.batch_no} 当前状态为 {batch.batch_status.value}，"
            "仅 SUCCEEDED 或 ROLLBACK_PREVIEW 状态的批次可以执行撤销"
        )

    ops = _load_operations(db, batch_id)
    conflicts = _check_conflicts(db, ops)

    # P0: 只要存在冲突 → 不执行任何撤销
    if conflicts:
        conflict_messages = [c["reason"] for c in conflicts]
        raise Conflict(
            f"批次 {batch.batch_no} 存在 {len(conflicts)} 项数据冲突，"
            f"无法执行撤销。请处理冲突后重新尝试。\n"
            + "\n".join(f"  - {m}" for m in conflict_messages[:10])
        )

    rolled_back_count = 0
    skipped_count = 0
    details: list[dict[str, Any]] = []

    # 逆序处理 —— 最后执行的操作最先撤销
    for op in reversed(ops):
        employee_name = _get_employee_name(db, op.employee_id)

        if not op.reversible:
            skipped_count += 1
            details.append({
                "operation_id": op.id,
                "employee_id": op.employee_id,
                "employee_name": employee_name,
                "action": op.operation_type,
                "status": "skipped",
                "reason": op.irreversible_reason or "操作本身不可逆",
            })
            continue

        # 执行逆向操作 —— 如抛出异常，整个事务回滚
        _reverse_operation(db, op, operator)
        rolled_back_count += 1
        details.append({
            "operation_id": op.id,
            "employee_id": op.employee_id,
            "employee_name": employee_name,
            "action": op.operation_type,
            "status": "rolled_back",
            "reason": None,
        })

    # 所有操作成功后更新批次状态
    batch.batch_status = RosterBatchStatus.ROLLED_BACK
    batch.rolled_back_at = datetime.now()

    # 操作日志
    operator_id = operator.get("operator_id", "system")

    operation_log_service.create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.ROSTER_IMPORT.value,
        object_id=str(batch_id),
        operation_type="ROLLBACK",
        before_data={"batch_no": batch.batch_no, "status": RosterBatchStatus.SUCCEEDED.value},
        after_data={
            "batch_no": batch.batch_no,
            "status": RosterBatchStatus.ROLLED_BACK.value,
            "rolled_back_count": rolled_back_count,
            "skipped_count": skipped_count,
            "conflict_count": 0,
        },
        operation_source="roster_rollback",
        business_id=batch_id,
    )

    db.flush()

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "rolled_back_count": rolled_back_count,
        "skipped_count": skipped_count,
        "conflict_count": 0,
        "details": details,
    }


# ---------------------------------------------------------------------------
# 逆向操作实现
# ---------------------------------------------------------------------------


def _reverse_operation(
    db: DBSession,
    op: RosterImportOperation,
    operator: dict[str, Any],
) -> None:
    """执行单条操作的反向撤销。

    必须支持所有提交服务产生的 operation_type。不支持的抛出异常。
    """
    operator_id = operator.get("operator_id", "system")
    operator_name = operator.get("operator_name", "system")

    reverse_map: dict[str, Callable] = {
        "CREATE_EMPLOYEE": _reverse_create_employee,
        "CREATE_PROFILE": _reverse_create_profile,
        "CREATE_EMPLOYMENT": _reverse_create_employment,
        "UPDATE_EMPLOYEE": _reverse_update_field,
        "UPDATE_PROFILE": _reverse_update_field,
        "UPDATE_EMPLOYMENT": _reverse_update_field,
        "CREATE_NOTE": _reverse_create_note,
        "CREATE_CONFIRMATION": _reverse_create_confirmation,
        "CREATE_CONTRACT": _reverse_create_contract,
        "CREATE_FINANCIAL_ACCOUNT": _reverse_create_financial_account,
        "CREATE_COMPENSATION": _reverse_create_compensation,
        "CREATE_ASSESSMENT": _reverse_create_assessment,
    }

    reverse_func = reverse_map.get(op.operation_type)
    if reverse_func is None:
        raise InvalidStateTransition(
            f"不支持撤销操作类型: {op.operation_type}（操作 ID: {op.id}）"
        )

    reverse_func(db, op, operator_name)

    # 记录反向操作条目
    reverse_op_record = RosterImportOperation(
        batch_id=op.batch_id,
        row_id=op.row_id,
        employee_id=op.employee_id,
        operation_type=f"REVERSE_{op.operation_type}",
        target_table=op.target_table,
        target_id=op.target_id,
        before_snapshot_json=op.after_snapshot_json,
        after_snapshot_json=op.before_snapshot_json,
        reversible=False,
        irreversible_reason="反向撤销记录，不可再次撤销",
    )
    db.add(reverse_op_record)

    operation_log_service.create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.ROSTER_IMPORT.value,
        object_id=str(op.batch_id),
        operation_type=f"REVERSE_{op.operation_type}",
        before_data=json.loads(op.after_snapshot_json) if op.after_snapshot_json else None,
        after_data=json.loads(op.before_snapshot_json) if op.before_snapshot_json else None,
        operation_source="roster_rollback",
        business_id=op.batch_id,
    )


def _reverse_create_employee(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_EMPLOYEE 操作。"""
    if op.target_table != "employee" or op.target_id is None:
        raise Conflict("无效的 CREATE_EMPLOYEE 操作记录")

    employee = db.query(Employee).filter(
        Employee.id == op.target_id,
        Employee.is_deleted == False,
    ).first()
    if not employee:
        raise Conflict(f"员工记录不存在或已逻辑删除: {op.target_id}")

    if _has_downstream_records(db, op.target_id):
        raise Conflict(f"员工 {op.target_id} 存在下游业务记录，无法自动删除")

    employee.is_deleted = True
    employee.deleted_at = datetime.now()
    employee.deleted_by = operator_name
    employee.employee_status = EmployeeStatus.ARCHIVED


def _reverse_create_profile(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_PROFILE 操作。"""
    if op.target_table != "employee_profile" or op.target_id is None:
        raise Conflict("无效的 CREATE_PROFILE 操作记录")

    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id == op.target_id,
        EmployeeProfile.is_deleted == False,
    ).first()
    if profile:
        profile.is_deleted = True
        profile.deleted_at = datetime.now()
        profile.deleted_by = operator_name


def _reverse_create_employment(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_EMPLOYMENT 操作。"""
    if op.target_table != "employment_record" or op.target_id is None:
        raise Conflict("无效的 CREATE_EMPLOYMENT 操作记录")

    emp = db.query(EmploymentRecord).filter(
        EmploymentRecord.id == op.target_id,
        EmploymentRecord.is_deleted == False,
    ).first()
    if emp:
        emp.is_deleted = True
        emp.deleted_at = datetime.now()
        emp.deleted_by = operator_name


def _reverse_create_contract(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_CONTRACT 操作。"""
    if op.target_table != "employment_contract" or op.target_id is None:
        raise Conflict("无效的 CREATE_CONTRACT 操作记录")

    contract = db.query(EmploymentContract).filter(
        EmploymentContract.id == op.target_id,
        EmploymentContract.is_deleted == False,
    ).first()
    if contract:
        contract.is_deleted = True
        contract.deleted_at = datetime.now()
        contract.deleted_by = operator_name


def _reverse_create_financial_account(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_FINANCIAL_ACCOUNT 操作。

    先检查账户是否已被 HR 确认（已确认的账户不可撤销）。
    """
    if op.target_table != "employee_financial_account" or op.target_id is None:
        raise Conflict("无效的 CREATE_FINANCIAL_ACCOUNT 操作记录")

    account = db.query(EmployeeFinancialAccount).filter(
        EmployeeFinancialAccount.id == op.target_id,
        EmployeeFinancialAccount.is_deleted == False,
    ).first()

    if account:
        # 已确认的账户不可撤销
        if account.confirmed_at is not None:
            raise Conflict(
                f"账户 {account.account_no} 已被 HR 确认，不可自动撤销"
            )
        account.is_deleted = True
        account.deleted_at = datetime.now()
        account.deleted_by = operator_name


def _reverse_create_compensation(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_COMPENSATION 操作。"""
    if op.target_table != "compensation_record" or op.target_id is None:
        raise Conflict("无效的 CREATE_COMPENSATION 操作记录")

    comp = db.query(CompensationRecord).filter(
        CompensationRecord.id == op.target_id,
    ).first()
    if comp:
        db.delete(comp)


def _reverse_create_assessment(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 CREATE_ASSESSMENT 操作。"""
    if op.target_table != "employee_assessment" or op.target_id is None:
        raise Conflict("无效的 CREATE_ASSESSMENT 操作记录")

    assessment = db.query(EmployeeAssessment).filter(
        EmployeeAssessment.id == op.target_id,
    ).first()
    if assessment:
        db.delete(assessment)


def _reverse_update_field(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 UPDATE_* 操作。"""
    if op.target_id is None or not op.before_snapshot_json:
        raise Conflict("缺少必要的前置快照数据")

    model_class = _TABLE_MODEL_MAP.get(op.target_table)
    if model_class is None:
        raise Conflict(f"不支持的目标表: {op.target_table}")

    before_data = _parse_json_safe(op.before_snapshot_json)
    if not before_data:
        raise Conflict("前置快照数据格式异常")

    record = db.query(model_class).filter(
        model_class.id == op.target_id,
    ).first()
    if record is None:
        raise Conflict(f"目标记录不存在（{op.target_table}: {op.target_id}）")

    for field_name, before_value in before_data.items():
        if field_name in _SYSTEM_FIELDS:
            continue
        if not hasattr(record, field_name):
            continue

        setattr(record, field_name, before_value)

        category = _get_attribute_category(op.target_table)
        after_value = _parse_json_safe(op.after_snapshot_json, {}).get(field_name)

        history = EmployeeAttributeHistory(
            employee_id=op.employee_id,
            employment_id=record.id if op.target_table == "employment_record" else None,
            category=category,
            field_name=field_name,
            before_value_json=json.dumps(after_value, ensure_ascii=False),
            after_value_json=json.dumps(before_value, ensure_ascii=False),
            source_type=AttributeSource.MANUAL,
            source_id=f"rollback_{op.batch_id}",
            import_batch_id=op.batch_id,
            operator_name=operator_name,
        )
        db.add(history)


def _reverse_create_note(
    db: DBSession,
    op: RosterImportOperation,
) -> None:
    """撤销 CREATE_NOTE 操作。"""
    if op.target_table != "employee_note" or op.target_id is None:
        raise Conflict("无效的 CREATE_NOTE 操作记录")

    note = db.query(EmployeeNote).filter(
        EmployeeNote.id == op.target_id,
    ).first()
    if note is None:
        raise Conflict("备注记录不存在")

    db.delete(note)


def _reverse_create_confirmation(
    db: DBSession,
    op: RosterImportOperation,
) -> None:
    """撤销 CREATE_CONFIRMATION 操作。

    仅当确认项仍为 PENDING 状态时允许删除。
    """
    if op.target_table != "hr_confirmation_item" or op.target_id is None:
        raise Conflict("无效的 CREATE_CONFIRMATION 操作记录")

    confirmation = db.query(HrConfirmationItem).filter(
        HrConfirmationItem.id == op.target_id,
    ).first()
    if confirmation is None:
        raise Conflict("HR 确认项不存在")

    if confirmation.item_status != ConfirmationItemStatus.PENDING:
        raise Conflict(
            f"HR 确认项已处理（状态: {confirmation.item_status.value}），不可撤销"
        )

    db.delete(confirmation)


# ---------------------------------------------------------------------------
# 冲突检查
# ---------------------------------------------------------------------------


def _check_conflicts(
    db: DBSession,
    ops: list[RosterImportOperation],
) -> list[dict[str, Any]]:
    """检查操作是否与当前数据库数据存在冲突。

    对于每条操作，读取 after_snapshot_json 并与当前数据库记录比对。
    如果记录已被修改（与快照不一致），则判定为冲突。
    """
    conflicts: list[dict[str, Any]] = []

    for op in ops:
        if not op.reversible:
            continue

        if op.after_snapshot_json is None:
            continue

        after_data = _parse_json_safe(op.after_snapshot_json, {})
        if not after_data:
            continue

        model_class = _TABLE_MODEL_MAP.get(op.target_table)
        if model_class is None:
            continue

        record = db.query(model_class).filter(
            model_class.id == op.target_id,
        ).first()

        if record is None:
            conflicts.append({
                "operation_id": op.id,
                "reason": f"目标记录不存在（{op.target_table}: {op.target_id}），"
                "可能已被人工删除",
            })
            continue

        mismatches: list[str] = []
        for field_name, expected_value in after_data.items():
            if field_name in _SYSTEM_FIELDS:
                continue
            if not hasattr(record, field_name):
                continue

            current_value = getattr(record, field_name)
            if not _values_match(current_value, expected_value):
                mismatches.append(
                    f"{field_name}: 期望={expected_value!r}, 实际={current_value!r}"
                )

        if mismatches:
            reason_detail = "; ".join(mismatches)
            conflicts.append({
                "operation_id": op.id,
                "reason": f"数据已被人工修改（{reason_detail}）",
            })

    return conflicts


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------


def _has_downstream_records(db: DBSession, employee_id: int) -> bool:
    """检查员工是否存在下游业务记录。"""
    if db.query(EmploymentRecord).filter(
        EmploymentRecord.employee_id == employee_id,
        EmploymentRecord.is_deleted == False,
    ).first():
        return True

    if db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id == employee_id,
        EmployeeProfile.is_deleted == False,
    ).first():
        return True

    if db.query(EmployeeFinancialAccount).filter(
        EmployeeFinancialAccount.employee_id == employee_id,
        EmployeeFinancialAccount.is_deleted == False,
    ).first():
        return True

    if db.query(EmploymentContract).filter(
        EmploymentContract.employee_id == employee_id,
        EmploymentContract.is_deleted == False,
    ).first():
        return True

    if db.query(EmployeeNote).filter(
        EmployeeNote.employee_id == employee_id,
    ).first():
        return True

    if db.query(HrConfirmationItem).filter(
        HrConfirmationItem.employee_id == employee_id,
    ).first():
        return True

    if db.query(CompensationRecord).filter(
        CompensationRecord.employee_id == employee_id,
    ).first():
        return True

    if db.query(EmployeeAssessment).filter(
        EmployeeAssessment.employee_id == employee_id,
    ).first():
        return True

    if db.query(SystemTodo).filter(
        SystemTodo.business_type == OperationObjectType.EMPLOYEE.value,
        SystemTodo.business_id == employee_id,
        SystemTodo.is_deleted == False,
    ).first():
        return True

    return False


def _get_employee_name(db: DBSession, employee_id: int | None) -> str:
    if employee_id is None:
        return "未知"
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        return f"已删除员工(ID={employee_id})"
    return employee.name


def _load_batch(db: DBSession, batch_id: int) -> RosterImportBatch:
    batch = db.query(RosterImportBatch).filter(
        RosterImportBatch.id == batch_id,
    ).first()
    if batch is None:
        raise ResourceNotFound(f"导入批次不存在: {batch_id}")
    return batch


def _load_operations(
    db: DBSession,
    batch_id: int,
) -> list[RosterImportOperation]:
    return (
        db.query(RosterImportOperation)
        .filter(RosterImportOperation.batch_id == batch_id)
        .order_by(RosterImportOperation.id.asc())
        .all()
    )


def _build_operation_details(op: RosterImportOperation) -> str:
    """生成操作的可读描述。"""
    after_data = _parse_json_safe(op.after_snapshot_json, {})

    if op.operation_type == "CREATE_EMPLOYEE":
        name = after_data.get("name", "未知")
        return f"创建员工: {name}"

    if op.operation_type == "CREATE_EMPLOYMENT":
        return "创建任职记录"

    if op.operation_type == "CREATE_PROFILE":
        return "创建员工档案"

    if op.operation_type in ("UPDATE_EMPLOYEE", "UPDATE_PROFILE", "UPDATE_EMPLOYMENT"):
        fields = ", ".join(after_data.keys()) if after_data else "未知字段"
        return f"更新字段 [{fields}]（{op.target_table}）"

    if op.operation_type == "CREATE_NOTE":
        content = after_data.get("content", "")
        preview = content[:50] + "..." if len(content) > 50 else content
        return f"创建备注: {preview}"

    if op.operation_type == "CREATE_CONFIRMATION":
        title = after_data.get("title", "未知")
        return f"创建 HR 确认项: {title}"

    if op.operation_type == "CREATE_CONTRACT":
        return "创建合同"

    if op.operation_type == "CREATE_FINANCIAL_ACCOUNT":
        acct_type = after_data.get("account_type", "未知")
        return f"创建{acct_type}账号"

    if op.operation_type == "CREATE_COMPENSATION":
        return "创建薪酬记录"

    if op.operation_type == "CREATE_ASSESSMENT":
        return "创建测评记录"

    return f"{op.operation_type} -> {op.target_table}"


def _parse_json_safe(
    value: str | None,
    default: Any = None,
) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _values_match(current: Any, expected: Any) -> bool:
    if current is None and expected is None:
        return True
    if current is None or expected is None:
        return False
    return str(current) == str(expected)


def _get_attribute_category(target_table: str) -> str | None:
    CATEGORY_MAP = {
        "employee": "employee",
        "employment_record": "employment",
        "employee_profile": "profile",
        "employee_financial_account": "financial",
        "employment_contract": "contract",
        "compensation_record": "compensation",
        "employee_assessment": "assessment",
    }
    return CATEGORY_MAP.get(target_table)

"""花名册导入撤销服务。"""

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
# 常量
# ---------------------------------------------------------------------------

# 不可逆的操作类型 —— 这些操作即使 reversible=True 也应当被视为不可逆
IRREVERSIBLE_SOURCE_TYPES: set[str] = {
    "REGULARIZATION",
    "CONFIRMED_SEPARATION",
    "CONFIRMED_CONTRACT",
    "CONFIRMED_ACCOUNT",
}

# 系统字段 —— 冲突检查时跳过这些字段
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

# 表名 -> SQLAlchemy 模型映射
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
    if batch.batch_status != RosterBatchStatus.SUCCEEDED:
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

    # 组装按员工分组的 items
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

    加载批次及其所有操作，检查冲突，按逆序逐条撤销可逆且无冲突的操作，
    更新批次状态为 ROLLED_BACK，并记录操作日志。

    Parameters
    ----------
    db : DBSession
        数据库会话。
    batch_id : int
        要撤销的批次 ID。
    operator : dict
        操作人信息，至少包含 operator_id 和 operator_name。

    Returns
    -------
    dict
        撤销结果统计。
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
    conflict_map = {c["operation_id"]: c for c in conflicts}

    rolled_back_count = 0
    skipped_count = 0
    conflict_count = len(conflicts)
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

        conflict_info = conflict_map.get(op.id)
        if conflict_info:
            conflict_count += 1
            details.append({
                "operation_id": op.id,
                "employee_id": op.employee_id,
                "employee_name": employee_name,
                "action": op.operation_type,
                "status": "conflict",
                "reason": conflict_info["reason"],
            })
            continue

        # 执行逆向操作
        try:
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
        except Exception:
            conflict_count += 1
            details.append({
                "operation_id": op.id,
                "employee_id": op.employee_id,
                "employee_name": employee_name,
                "action": op.operation_type,
                "status": "error",
                "reason": "撤销执行异常，请人工处理",
            })

    # 更新批次状态
    batch.batch_status = RosterBatchStatus.ROLLED_BACK
    batch.rolled_back_at = datetime.now()

    # 记录操作日志
    operator_id = operator.get("operator_id", "system")
    operator_name = operator.get("operator_name", "system")

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
            "conflict_count": conflict_count,
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
        "conflict_count": conflict_count,
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

    根据 operation_type 执行不同的逆向逻辑，并在完成后记录反向操作条目和操作日志。

    Raises
    ------
    Conflict
        当数据已被修改无法安全撤销时抛出。
    """
    operator_id = operator.get("operator_id", "system")
    operator_name = operator.get("operator_name", "system")

    if op.operation_type == "CREATE_EMPLOYEE":
        _reverse_create_employee(db, op, operator_name)
    elif op.operation_type == "UPDATE_FIELD":
        _reverse_update_field(db, op, operator_name)
    elif op.operation_type == "CREATE_NOTE":
        _reverse_create_note(db, op)
    elif op.operation_type == "CREATE_CONFIRMATION":
        _reverse_create_confirmation(db, op)
    else:
        # 未知操作类型 —— 设为不可逆
        op.reversible = False
        op.irreversible_reason = f"不支持撤销操作类型: {op.operation_type}"

    # 记录反向操作条目（追踪审计用）
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

    # 记录操作日志
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
    """撤销 CREATE_EMPLOYEE 操作。

    检查员工是否存在下游业务记录：
    - 无下游记录：逻辑删除员工，状态置为 ARCHIVED。
    - 有下游记录：标记为冲突，不可自动撤销。
    """
    if op.target_table != "employee" or op.target_id is None:
        op.reversible = False
        op.irreversible_reason = "无效的 CREATE_EMPLOYEE 操作记录"
        return

    employee = db.query(Employee).filter(
        Employee.id == op.target_id,
        Employee.is_deleted == False,
    ).first()
    if not employee:
        op.reversible = False
        op.irreversible_reason = "员工记录不存在或已逻辑删除"
        return

    if _has_downstream_records(db, op.target_id):
        op.reversible = False
        op.irreversible_reason = "员工存在下游业务记录，无法自动删除"
        return

    # 逻辑删除员工
    employee.is_deleted = True
    employee.deleted_at = datetime.now()
    employee.deleted_by = operator_name
    employee.employee_status = EmployeeStatus.ARCHIVED


def _reverse_update_field(
    db: DBSession,
    op: RosterImportOperation,
    operator_name: str,
) -> None:
    """撤销 UPDATE_FIELD 操作。

    将目标记录的字段恢复为 before_snapshot_json 中的值，
    并创建属性变更历史条目。
    """
    if op.target_id is None or not op.before_snapshot_json:
        op.reversible = False
        op.irreversible_reason = "缺少必要的前置快照数据"
        return

    model_class = _TABLE_MODEL_MAP.get(op.target_table)
    if model_class is None:
        op.reversible = False
        op.irreversible_reason = f"不支持的目标表: {op.target_table}"
        return

    before_data = _parse_json_safe(op.before_snapshot_json)
    if not before_data:
        op.reversible = False
        op.irreversible_reason = "前置快照数据格式异常"
        return

    # 加载目标记录
    record = db.query(model_class).filter(
        model_class.id == op.target_id,
    ).first()
    if record is None:
        op.reversible = False
        op.irreversible_reason = f"目标记录不存在（{op.target_table}: {op.target_id}）"
        return

    # 逐字段恢复 before 值
    for field_name, before_value in before_data.items():
        if field_name in _SYSTEM_FIELDS:
            continue
        if not hasattr(record, field_name):
            continue

        setattr(record, field_name, before_value)

        # 创建属性变更历史
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
    """撤销 CREATE_NOTE 操作。

    删除（硬删除）由导入创建的备注记录。EmployeeNote 模型不包含 is_deleted 字段，
    故直接执行硬删除。
    """
    if op.target_table != "employee_note" or op.target_id is None:
        op.reversible = False
        op.irreversible_reason = "无效的 CREATE_NOTE 操作记录"
        return

    note = db.query(EmployeeNote).filter(
        EmployeeNote.id == op.target_id,
    ).first()
    if note is None:
        op.reversible = False
        op.irreversible_reason = "备注记录不存在"
        return

    db.delete(note)


def _reverse_create_confirmation(
    db: DBSession,
    op: RosterImportOperation,
) -> None:
    """撤销 CREATE_CONFIRMATION 操作。

    HR 确认项通常不可逆 —— 特别是已确认的确认项。
    仅当确认项仍为 PENDING 状态时允许删除。
    """
    if op.target_table != "hr_confirmation_item" or op.target_id is None:
        op.reversible = False
        op.irreversible_reason = "无效的 CREATE_CONFIRMATION 操作记录"
        return

    confirmation = db.query(HrConfirmationItem).filter(
        HrConfirmationItem.id == op.target_id,
    ).first()
    if confirmation is None:
        op.reversible = False
        op.irreversible_reason = "HR 确认项不存在"
        return

    if confirmation.item_status != ConfirmationItemStatus.PENDING:
        op.reversible = False
        op.irreversible_reason = (
            f"HR 确认项已处理（状态: {confirmation.item_status.value}），不可撤销"
        )
        return

    # 检查是否属于绝对不可逆的类型
    if confirmation.source_type in IRREVERSIBLE_SOURCE_TYPES:
        op.reversible = False
        op.irreversible_reason = f"确认类型 {confirmation.source_type} 属于不可逆操作"
        return

    # PENDING 且非绝对不可逆类型 —— 可以删除
    db.delete(confirmation)


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------


def _check_conflicts(
    db: DBSession,
    ops: list[RosterImportOperation],
) -> list[dict[str, Any]]:
    """检查操作是否与当前数据库数据存在冲突。

    对于每条操作，读取 after_snapshot_json 并与当前数据库记录比对。
    如果记录已被修改（与快照不一致），则判定为冲突。

    Returns
    -------
    list[dict]
        每个元素包含 operation_id 和 reason。
    """
    conflicts: list[dict[str, Any]] = []

    for op in ops:
        if op.after_snapshot_json is None:
            continue

        after_data = _parse_json_safe(op.after_snapshot_json, {})
        if not after_data:
            continue

        model_class = _TABLE_MODEL_MAP.get(op.target_table)
        if model_class is None:
            continue

        # 加载当前记录
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

        # 逐字段比对
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


def _has_downstream_records(db: DBSession, employee_id: int) -> bool:
    """检查员工是否存在下游业务记录。

    遍历可能引用该员工的各种业务表，检测是否存在关联记录。
    返回 True 表示存在至少一条下游记录，此时不应自动删除员工。
    """
    # 1. 任职记录（逻辑删除的不算）
    employment = db.query(EmploymentRecord).filter(
        EmploymentRecord.employee_id == employee_id,
        EmploymentRecord.is_deleted == False,
    ).first()
    if employment:
        return True

    # 2. 员工档案
    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id == employee_id,
        EmployeeProfile.is_deleted == False,
    ).first()
    if profile:
        return True

    # 3. 财务账户
    account = db.query(EmployeeFinancialAccount).filter(
        EmployeeFinancialAccount.employee_id == employee_id,
        EmployeeFinancialAccount.is_deleted == False,
    ).first()
    if account:
        return True

    # 4. 劳动合同
    contract = db.query(EmploymentContract).filter(
        EmploymentContract.employee_id == employee_id,
        EmploymentContract.is_deleted == False,
    ).first()
    if contract:
        return True

    # 以下模型不包含 is_deleted 字段，直接检测记录存在性

    # 5. 备注
    note = db.query(EmployeeNote).filter(
        EmployeeNote.employee_id == employee_id,
    ).first()
    if note:
        return True

    # 6. HR 确认项
    confirmation = db.query(HrConfirmationItem).filter(
        HrConfirmationItem.employee_id == employee_id,
    ).first()
    if confirmation:
        return True

    # 7. 薪酬记录
    compensation = db.query(CompensationRecord).filter(
        CompensationRecord.employee_id == employee_id,
    ).first()
    if compensation:
        return True

    # 8. 测评记录
    assessment = db.query(EmployeeAssessment).filter(
        EmployeeAssessment.employee_id == employee_id,
    ).first()
    if assessment:
        return True

    # 9. 系统待办
    todo = db.query(SystemTodo).filter(
        SystemTodo.business_type == OperationObjectType.EMPLOYEE.value,
        SystemTodo.business_id == employee_id,
        SystemTodo.is_deleted == False,
    ).first()
    if todo:
        return True

    return False


def _get_employee_name(db: DBSession, employee_id: int | None) -> str:
    """根据员工 ID 获取员工姓名。"""
    if employee_id is None:
        return "未知"

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        return f"已删除员工(ID={employee_id})"

    return employee.name


def _load_batch(db: DBSession, batch_id: int) -> RosterImportBatch:
    """加载导入批次，不存在时抛出 ResourceNotFound。"""
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
    """加载指定批次的所有操作记录（按创建时间升序）。"""
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

    if op.operation_type == "UPDATE_FIELD":
        fields = ", ".join(after_data.keys()) if after_data else "未知字段"
        return f"更新字段 [{fields}]（{op.target_table}）"

    if op.operation_type == "CREATE_NOTE":
        content = after_data.get("content", "")
        preview = content[:50] + "..." if len(content) > 50 else content
        return f"创建备注: {preview}"

    if op.operation_type == "CREATE_CONFIRMATION":
        title = after_data.get("title", "未知")
        return f"创建 HR 确认项: {title}"

    return f"{op.operation_type} -> {op.target_table}"


def _parse_json_safe(
    value: str | None,
    default: Any = None,
) -> Any:
    """安全解析 JSON 字符串，解析失败返回默认值。"""
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _values_match(current: Any, expected: Any) -> bool:
    """比较两个值是否匹配（处理类型不匹配的情况）。"""
    if current is None and expected is None:
        return True
    if current is None or expected is None:
        return False

    # 使用字符串形式比较，避免类型差异（如 int vs str）
    return str(current) == str(expected)


def _get_attribute_category(target_table: str) -> str | None:
    """根据目标表名返回属性变更的类别。"""
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

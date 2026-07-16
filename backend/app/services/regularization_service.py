from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    EmploymentStatus,
    OperationObjectType,
    ProbationStatus,
    RegularizationDecision,
    TodoStatus,
)
from ..exceptions import (
    Conflict,
    InvalidStateTransition,
    ResourceNotFound,
)
from ..models import EmploymentRecord, RegularizationRecord, SystemTodo
from .operation_log_service import create_log


def _to_dict(model) -> dict[str, Any]:
    return model.dict()


def _get_employment(db: DBSession, employment_id: int) -> EmploymentRecord:
    emp = db.query(EmploymentRecord).filter(
        EmploymentRecord.id == employment_id,
        EmploymentRecord.is_deleted == False,
    ).first()
    if not emp:
        raise ResourceNotFound(f"任职记录不存在: {employment_id}")
    return emp


def preview_regularization(db: DBSession, employment_id: int) -> dict[str, Any]:
    """转正前预览。"""
    emp = _get_employment(db, employment_id)

    warnings = []
    if emp.probation_status not in (ProbationStatus.PENDING_REVIEW, ProbationStatus.IN_PROGRESS):
        if emp.probation_status == ProbationStatus.REGULARIZED:
            warnings.append("员工已转正")
        elif emp.probation_status == ProbationStatus.FAILED:
            warnings.append("员工试用期未通过")
        elif emp.probation_status == ProbationStatus.TERMINATED:
            warnings.append("员工试用期已终止")

    can_regularize = emp.probation_status in (
        ProbationStatus.PENDING_REVIEW, ProbationStatus.IN_PROGRESS
    )

    return {
        "employment_id": emp.id,
        "hire_date": emp.hire_date,
        "probation_start_date": emp.probation_start_date,
        "probation_end_date": emp.probation_end_date,
        "probation_status": emp.probation_status.value if hasattr(emp.probation_status, "value") else emp.probation_status,
        "has_completed_final_review": False,
        "final_review": None,
        "can_regularize": can_regularize,
        "warnings": warnings,
    }


def confirm_regularization(
    db: DBSession,
    employment_id: int,
    data: dict[str, Any],
    operator: dict[str, str],
) -> dict[str, Any]:
    """转正确认。"""
    emp = _get_employment(db, employment_id)

    # 检查任职状态
    if emp.probation_status not in (ProbationStatus.PENDING_REVIEW, ProbationStatus.IN_PROGRESS):
        raise InvalidStateTransition(f"当前试用期状态不允许转正: {emp.probation_status}")

    decision_str = data["decision"].value if hasattr(data["decision"], "value") else data["decision"]
    operator_id = operator.get("user_id", "system")
    now = datetime.now()

    # 拒绝 EXTENDED 决策
    if decision_str == RegularizationDecision.EXTENDED.value:
        raise InvalidStateTransition("转正不支持试用期延长决策")

    # 幂等检查：同一任职只能有一条生效的 APPROVED
    if decision_str == RegularizationDecision.APPROVED.value:
        existing = db.query(RegularizationRecord).filter(
            RegularizationRecord.employment_id == employment_id,
            RegularizationRecord.decision == RegularizationDecision.APPROVED.value,
            RegularizationRecord.is_effective == True,
            RegularizationRecord.is_deleted == False,
        ).first()
        if existing:
            raise Conflict("该员工已转正，请勿重复操作")

    before_emp = _to_dict(emp)

    # 计算转正生效日期（从入参、任职记录的预计转正日期或今天）
    effective_date = data.get("effective_date") or emp.expected_regularization_date or date.today()

    # 创建转正记录
    record = RegularizationRecord(
        employment_id=emp.id,
        decision=decision_str,
        effective_date=effective_date,
        new_probation_end_date=data.get("new_probation_end_date"),
        decision_reason=data.get("decision_reason"),
        ai_summary_version_id=data.get("ai_summary_version_id"),
        confirmed_by=operator_id,
        confirmed_at=now,
        is_effective=True,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(record)

    # 更新任职状态
    if decision_str == RegularizationDecision.APPROVED.value:
        emp.probation_status = ProbationStatus.REGULARIZED
        emp.employment_status = EmploymentStatus.ACTIVE
        emp.regularization_date = effective_date
        emp.actual_regularization_date = data.get("actual_regularization_date") or date.today()

        # 完成相关待办
        pending_todos = db.query(SystemTodo).filter(
            SystemTodo.business_id == employment_id,
            SystemTodo.todo_status == TodoStatus.PENDING.value,
            SystemTodo.is_deleted == False,
        ).all()
        for todo in pending_todos:
            todo.todo_status = TodoStatus.COMPLETED.value
            todo.updated_by = operator_id
            todo.updated_at = now
    elif decision_str == RegularizationDecision.NOT_APPROVED.value:
        emp.probation_status = ProbationStatus.FAILED

        # 取消相关待办
        pending_todos = db.query(SystemTodo).filter(
            SystemTodo.business_id == employment_id,
            SystemTodo.todo_status == TodoStatus.PENDING.value,
            SystemTodo.is_deleted == False,
        ).all()
        for todo in pending_todos:
            todo.todo_status = TodoStatus.CANCELLED.value
            todo.updated_by = operator_id
            todo.updated_at = now

    emp.updated_by = operator_id
    emp.updated_at = now

    db.flush()

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.REGULARIZATION.value,
        object_id=str(record.id),
        operation_type="CONFIRM",
        before_data=json.dumps(before_emp, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(emp), default=str, ensure_ascii=False),
        business_id=emp.id,
    )

    db.flush()
    return _to_dict(record)


def get_records(db: DBSession, employment_id: int) -> list[dict[str, Any]]:
    """获取转正记录列表。"""
    records = db.query(RegularizationRecord).filter(
        RegularizationRecord.employment_id == employment_id,
        RegularizationRecord.is_deleted == False,
    ).order_by(RegularizationRecord.created_at.desc()).all()
    return [_to_dict(r) for r in records]

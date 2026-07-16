from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    EmploymentStatus,
    FollowupTaskStatus,
    OperationObjectType,
    ProbationStatus,
    TodoStatus,
)
from ..exceptions import InvalidStateTransition, ResourceNotFound
from ..models import EmploymentRecord, FollowupTask, SeparationRecord, SystemTodo
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


def preview_separation(db: DBSession, employment_id: int) -> dict[str, Any]:
    """离职预览。"""
    emp = _get_employment(db, employment_id)

    pending_tasks = db.query(FollowupTask).filter(
        FollowupTask.employment_id == employment_id,
        FollowupTask.followup_status.in_([
            FollowupTaskStatus.PENDING.value,
            FollowupTaskStatus.IN_PROGRESS.value,
        ]),
        FollowupTask.is_deleted == False,
    ).count()

    pending_todos = db.query(SystemTodo).filter(
        SystemTodo.business_id == employment_id,
        SystemTodo.todo_status == TodoStatus.PENDING.value,
        SystemTodo.is_deleted == False,
    ).count()

    warnings = []
    if emp.employment_status == EmploymentStatus.SEPARATED:
        warnings.append("该员工已离职")

    can_start = emp.employment_status not in (
        EmploymentStatus.SEPARATED,
    )

    return {
        "employment_id": emp.id,
        "employment_status": emp.employment_status.value if hasattr(emp.employment_status, "value") else emp.employment_status,
        "hire_date": emp.hire_date,
        "probation_status": emp.probation_status.value if hasattr(emp.probation_status, "value") else emp.probation_status,
        "pending_tasks_count": pending_tasks,
        "pending_todos_count": pending_todos,
        "can_start_separation": can_start,
        "warnings": warnings,
    }


def start_separation(
    db: DBSession,
    employment_id: int,
    data: dict[str, Any],
    operator: dict[str, str],
) -> dict[str, Any]:
    """启动离职流程。"""
    emp = _get_employment(db, employment_id)

    if emp.employment_status in (EmploymentStatus.SEPARATED,):
        raise InvalidStateTransition("员工已离职，不可重复操作")

    now = datetime.now()
    operator_id = operator.get("user_id", "system")
    before = _to_dict(emp)

    # 更新任职状态
    emp.employment_status = EmploymentStatus.SEPARATING
    emp.updated_by = operator_id
    emp.updated_at = now

    # 创建分离记录
    record = SeparationRecord(
        employment_id=emp.id,
        planned_separation_date=data.get("planned_separation_date"),
        separation_type=data.get("separation_type"),
        reason=data.get("reason"),
        hr_comment=data.get("hr_comment"),
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(record)
    db.flush()

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.SEPARATION.value,
        object_id=str(record.id),
        operation_type="START",
        before_data=json.dumps(before, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(emp), default=str, ensure_ascii=False),
        business_id=emp.id,
    )

    db.flush()
    return _to_dict(record)


def confirm_separation(
    db: DBSession,
    employment_id: int,
    data: dict[str, Any],
    operator: dict[str, str],
) -> dict[str, Any]:
    """确认离职。"""
    emp = _get_employment(db, employment_id)

    if emp.employment_status != EmploymentStatus.SEPARATING:
        raise InvalidStateTransition("当前任职状态不允许确认离职，请先启动离职流程")

    now = datetime.now()
    operator_id = operator.get("user_id", "system")
    before_emp = _to_dict(emp)

    # 查找启动阶段的分离记录，获取计划离职日期
    start_record = db.query(SeparationRecord).filter(
        SeparationRecord.employment_id == employment_id,
        SeparationRecord.actual_separation_date.is_(None),
        SeparationRecord.confirmed_at.is_(None),
        SeparationRecord.is_deleted == False,
    ).order_by(SeparationRecord.created_at.desc()).first()
    planned_date = start_record.planned_separation_date if start_record else None

    # 创建离职确认记录
    record = SeparationRecord(
        employment_id=emp.id,
        planned_separation_date=planned_date,
        actual_separation_date=data.get("actual_separation_date") or planned_date or now.date(),
        separation_type=data.get("separation_type") or (start_record.separation_type if start_record else None),
        reason=data.get("reason") or (start_record.reason if start_record else None),
        hr_comment=data.get("hr_comment"),
        confirmed_by=operator_id,
        confirmed_at=now,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(record)

    # 更新任职状态
    emp.employment_status = EmploymentStatus.SEPARATED
    emp.separation_date = record.actual_separation_date
    if emp.probation_status in (ProbationStatus.IN_PROGRESS, ProbationStatus.PENDING_REVIEW):
        emp.probation_status = ProbationStatus.TERMINATED
    emp.updated_by = operator_id
    emp.updated_at = now

    # 取消未完成的跟进任务
    pending_tasks = db.query(FollowupTask).filter(
        FollowupTask.employment_id == employment_id,
        FollowupTask.followup_status.in_([
            FollowupTaskStatus.PENDING.value,
            FollowupTaskStatus.IN_PROGRESS.value,
            FollowupTaskStatus.PENDING_CONFIRMATION.value,
        ]),
        FollowupTask.is_deleted == False,
    ).all()
    task_ids = []
    for task in pending_tasks:
        task_ids.append(task.id)
        task.followup_status = FollowupTaskStatus.CANCELLED.value
        task.cancel_reason = "员工已离职"
        task.updated_by = operator_id
        task.updated_at = now

    # 取消未完成的待办
    pending_todos = db.query(SystemTodo).filter(
        SystemTodo.business_id == employment_id,
        SystemTodo.todo_status == TodoStatus.PENDING.value,
        SystemTodo.is_deleted == False,
    ).all()

    # 同时取消关联跟进任务的待办
    if task_ids:
        task_todos = db.query(SystemTodo).filter(
            SystemTodo.business_id.in_(task_ids),
            SystemTodo.todo_status == TodoStatus.PENDING.value,
            SystemTodo.is_deleted == False,
        ).all()
        pending_todos.extend(task_todos)

    for todo in pending_todos:
        todo.todo_status = TodoStatus.CANCELLED.value
        todo.updated_by = operator_id
        todo.updated_at = now

    db.flush()

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.SEPARATION.value,
        object_id=str(record.id),
        operation_type="CONFIRM",
        before_data=json.dumps(before_emp, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(emp), default=str, ensure_ascii=False),
        business_id=emp.id,
    )

    db.flush()
    return _to_dict(record)


def get_records(db: DBSession, employment_id: int) -> list[dict[str, Any]]:
    """获取离职记录列表。"""
    records = db.query(SeparationRecord).filter(
        SeparationRecord.employment_id == employment_id,
        SeparationRecord.is_deleted == False,
    ).order_by(SeparationRecord.created_at.desc()).all()
    return [_to_dict(r) for r in records]

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import OperationObjectType
from ..exceptions import ResourceNotFound, InvalidStateTransition, ValidationError
from ..models import EmploymentChange, EmploymentRecord
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


def create_change(
    db: DBSession,
    employment_id: int,
    data: dict[str, Any],
    operator: dict[str, str],
) -> dict[str, Any]:
    """创建异动记录。"""
    emp = _get_employment(db, employment_id)

    effective_date = data["effective_date"]

    # 校验日期：不早于入职
    if effective_date < emp.hire_date:
        raise ValidationError("异动生效日期不得早于入职日期", details={
            "effective_date": str(effective_date),
            "hire_date": str(emp.hire_date),
        })

    # 校验日期：不晚于离职
    if emp.separation_date and effective_date > emp.separation_date:
        raise ValidationError("异动生效日期不得晚于离职日期", details={
            "effective_date": str(effective_date),
            "separation_date": str(emp.separation_date),
        })

    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    # 如果未提供 before_data，自动从任职记录中获取当前值
    before_data = data.get("before_data")
    if before_data is None:
        before_data = _snapshot_employment(emp, data["change_type"])

    # 序列化 JSON 字段
    before_str = json.dumps(before_data, ensure_ascii=False) if before_data else None
    after_str = json.dumps(data.get("after_data"), ensure_ascii=False) if data.get("after_data") else None

    change_type_str = data["change_type"].value if hasattr(data["change_type"], "value") else data["change_type"]

    change = EmploymentChange(
        employment_id=emp.id,
        change_type=change_type_str,
        effective_date=effective_date,
        before_data=before_str,
        after_data=after_str,
        reason=data.get("reason"),
        confirmed_by=operator_id,
        confirmed_at=now,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(change)
    db.flush()

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.EMPLOYMENT_CHANGE.value,
        object_id=str(change.id),
        operation_type="CREATE",
        before_data=before_str,
        after_data=after_str,
        business_id=emp.id,
    )

    db.flush()
    return _to_dict(change)


def update_change(
    db: DBSession,
    change_id: int,
    data: dict[str, Any],
    operator: dict[str, str],
) -> dict[str, Any]:
    """更新异动记录。"""
    change = db.query(EmploymentChange).filter(
        EmploymentChange.id == change_id,
        EmploymentChange.is_deleted == False,
    ).first()
    if not change:
        raise ResourceNotFound(f"异动记录不存在: {change_id}")

    before = _to_dict(change)
    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    if "effective_date" in data:
        change.effective_date = data["effective_date"]
    if "after_data" in data:
        change.after_data = json.dumps(data["after_data"], ensure_ascii=False)
    if "reason" in data:
        change.reason = data["reason"]

    change.updated_by = operator_id
    change.updated_at = now

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.EMPLOYMENT_CHANGE.value,
        object_id=str(change.id),
        operation_type="UPDATE",
        before_data=json.dumps(before, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(change), default=str, ensure_ascii=False),
        business_id=change.employment_id,
    )

    db.flush()
    return _to_dict(change)


def get_change(db: DBSession, change_id: int) -> Optional[dict[str, Any]]:
    """获取异动详情。"""
    change = db.query(EmploymentChange).filter(
        EmploymentChange.id == change_id,
        EmploymentChange.is_deleted == False,
    ).first()
    if not change:
        return None
    return _to_dict(change)


def list_changes(db: DBSession, employment_id: int) -> list[dict[str, Any]]:
    """获取任职的异动记录列表。"""
    changes = db.query(EmploymentChange).filter(
        EmploymentChange.employment_id == employment_id,
        EmploymentChange.is_deleted == False,
    ).order_by(EmploymentChange.effective_date.desc()).all()
    return [_to_dict(c) for c in changes]


def _snapshot_employment(emp: EmploymentRecord, change_type: Any) -> dict[str, str]:
    """根据异动类型快照任职记录的当前值。"""
    change_type_str = change_type.value if hasattr(change_type, "value") else str(change_type)

    snapshot = {
        "department": emp.department,
        "position": emp.position,
        "manager_name": emp.manager_name,
    }

    # 只保留与异动类型相关的字段
    if change_type_str == "DEPARTMENT":
        return {"department": emp.department}
    elif change_type_str == "POSITION":
        return {"position": emp.position}
    elif change_type_str == "MANAGER":
        return {"manager_name": emp.manager_name}
    return snapshot

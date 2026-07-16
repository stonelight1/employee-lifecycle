from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from ..enums import OperationObjectType, TodoStatus
from ..exceptions import Conflict, DuplicateRequest, ResourceNotFound
from ..models import SystemTodo
from .operation_log_service import create_log


def _to_dict(model) -> dict[str, Any]:
    return model.dict()


def create_todo(db: DBSession, data: dict[str, Any]) -> dict[str, Any]:
    """创建待办（系统内部调用）。"""
    # 幂等性：idempotency_key 重复时返回已有记录
    idempotency_key = data.get("idempotency_key")
    if idempotency_key:
        existing = db.query(SystemTodo).filter(
            SystemTodo.idempotency_key == idempotency_key,
        ).first()
        if existing:
            return _to_dict(existing)

    now = datetime.now()
    operator_id = data.get("created_by", "system")

    todo = SystemTodo(
        user_id=data["user_id"],
        business_type=data["business_type"],
        business_id=data["business_id"],
        title=data["title"],
        due_at=data.get("due_at"),
        todo_status=TodoStatus.PENDING,
        priority=data.get("priority"),
        source=data.get("source"),
        idempotency_key=idempotency_key,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(todo)
    db.flush()

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.TODO.value,
        object_id=str(todo.id),
        operation_type="CREATE",
        after_data=_to_dict(todo),
        business_id=todo.business_id,
    )

    db.flush()
    return _to_dict(todo)


def complete_todo(db: DBSession, todo_id: int, operator: dict[str, str]) -> dict[str, Any]:
    """完成待办。"""
    todo = db.query(SystemTodo).filter(
        SystemTodo.id == todo_id,
        SystemTodo.is_deleted == False,
    ).first()
    if not todo:
        raise ResourceNotFound(f"待办不存在: {todo_id}")

    if todo.todo_status == TodoStatus.COMPLETED.value:
        raise Conflict("待办已完成，请勿重复操作")

    if todo.todo_status == TodoStatus.CANCELLED.value:
        raise Conflict("待办已取消，不可完成")

    before = _to_dict(todo)
    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    todo.todo_status = TodoStatus.COMPLETED.value
    todo.updated_by = operator_id
    todo.updated_at = now

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.TODO.value,
        object_id=str(todo.id),
        operation_type="COMPLETE",
        before_data=before,
        after_data=_to_dict(todo),
        business_id=todo.business_id,
    )

    db.flush()
    return _to_dict(todo)


def cancel_todo(db: DBSession, todo_id: int, reason: str, operator: dict[str, str]) -> dict[str, Any]:
    """取消待办。"""
    todo = db.query(SystemTodo).filter(
        SystemTodo.id == todo_id,
        SystemTodo.is_deleted == False,
    ).first()
    if not todo:
        raise ResourceNotFound(f"待办不存在: {todo_id}")

    if todo.todo_status == TodoStatus.CANCELLED.value:
        raise Conflict("待办已取消，请勿重复操作")

    if todo.todo_status == TodoStatus.COMPLETED.value:
        raise Conflict("待办已完成，不可取消")

    before = _to_dict(todo)
    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    todo.todo_status = TodoStatus.CANCELLED.value
    todo.updated_by = operator_id
    todo.updated_at = now

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.TODO.value,
        object_id=str(todo.id),
        operation_type="CANCEL",
        before_data=before,
        after_data=_to_dict(todo),
        business_id=todo.business_id,
    )

    db.flush()
    return _to_dict(todo)


def get_todo(db: DBSession, todo_id: int) -> Optional[dict[str, Any]]:
    """获取待办详情。"""
    todo = db.query(SystemTodo).filter(
        SystemTodo.id == todo_id,
        SystemTodo.is_deleted == False,
    ).first()
    if not todo:
        return None
    return _to_dict(todo)


def list_todos(
    db: DBSession,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    business_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """查询待办列表。"""
    query = db.query(SystemTodo).filter(
        SystemTodo.is_deleted == False,
    )

    if user_id:
        query = query.filter(SystemTodo.user_id == user_id)
    if status:
        query = query.filter(SystemTodo.todo_status == status)
    if business_type:
        query = query.filter(SystemTodo.business_type == business_type)

    total = query.count()

    items = query.order_by(
        SystemTodo.due_at.asc().nullslast(),
        SystemTodo.created_at.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()

    return [_to_dict(i) for i in items], total

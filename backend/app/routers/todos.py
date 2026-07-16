"""待办路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.common import ApiResponse
from ..schemas.todo_log import (
    TodoCancelRequest,
    TodoListResponse,
    TodoCompleteRequest,
    SystemTodoResponse,
)
from ..services.todo_service import (
    cancel_todo,
    complete_todo,
    get_todo,
    list_todos,
)

router = APIRouter(tags=["待办"])


@router.get(
    "/todos",
    response_model=ApiResponse[TodoListResponse],
)
def list_todos_route(
    user_id: str | None = Query(default=None, description="用户 ID"),
    status: str | None = Query(default=None, description="待办状态"),
    business_type: str | None = Query(default=None, description="业务类型"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取待办列表。"""
    items, total = list_todos(
        db, user_id=user_id, status=status, business_type=business_type,
        page=page, page_size=page_size,
    )
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/todos/{todo_id}",
    response_model=ApiResponse[SystemTodoResponse],
)
def get_todo_route(
    todo_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取待办详情。"""
    result = get_todo(db, todo_id)
    if result is None:
        raise ResourceNotFound(f"待办不存在: {todo_id}")
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/todos/{todo_id}/complete",
    response_model=ApiResponse[SystemTodoResponse],
)
def complete_todo_route(
    todo_id: int,
    body: TodoCompleteRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """完成待办。"""
    result = complete_todo(db, todo_id, current_user)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/todos/{todo_id}/cancel",
    response_model=ApiResponse[SystemTodoResponse],
)
def cancel_todo_route(
    todo_id: int,
    body: TodoCancelRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """取消待办。"""
    result = cancel_todo(db, todo_id, body.reason, current_user)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }

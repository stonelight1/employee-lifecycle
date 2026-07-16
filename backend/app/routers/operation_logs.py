"""操作日志路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.common import ApiResponse
from ..schemas.todo_log import (
    OperationLogListResponse,
    OperationLogResponse,
)
from ..services.operation_log_service import get_log, list_logs

router = APIRouter(tags=["操作日志"])


@router.get(
    "/operation-logs",
    response_model=ApiResponse[OperationLogListResponse],
)
def list_operation_logs_route(
    object_type: str | None = Query(default=None, description="对象类型"),
    object_id: str | None = Query(default=None, description="对象 ID"),
    business_id: int | None = Query(default=None, description="业务 ID"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取操作日志列表。"""
    items, total = list_logs(
        db,
        object_type=object_type,
        object_id=object_id,
        business_id=business_id,
        page=page,
        page_size=page_size,
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
    "/operation-logs/{log_id}",
    response_model=ApiResponse[OperationLogResponse],
)
def get_operation_log_route(
    log_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取操作日志详情。"""
    result = get_log(db, log_id)
    if result is None:
        raise ResourceNotFound(f"操作日志不存在: {log_id}")
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }

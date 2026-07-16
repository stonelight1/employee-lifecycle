"""HR 待确认事项路由。"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.common import ApiResponse
from ..schemas.hr_confirmation import (
    ConfirmActionRequest,
    ConfirmationItemResponse,
    ConfirmationListResponse,
)
from ..services.hr_confirmation_service import (
    confirm_item,
    get_confirmation_item,
    get_pending_count,
    ignore_item,
    list_confirmation_items,
    reject_item,
)
from ..services.operation_log_service import create_log

router = APIRouter(tags=["HR确认"])


@router.get(
    "/hr-confirmations",
    response_model=ApiResponse[ConfirmationListResponse],
)
def list_hr_confirmations_route(
    status: str | None = Query(default=None, description="状态过滤"),
    employee_id: int | None = Query(default=None, description="员工 ID"),
    import_batch_id: int | None = Query(default=None, description="导入批次 ID"),
    import_row_id: int | None = Query(default=None, description="导入行 ID"),
    issue_code: str | None = Query(default=None, description="问题代码过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取 HR 待确认事项列表。"""
    items, total, pending_count = list_confirmation_items(
        db,
        status=status,
        employee_id=employee_id,
        import_batch_id=import_batch_id,
        import_row_id=import_row_id,
        issue_code=issue_code,
        page=page,
        page_size=page_size,
    )
    pending_count = get_pending_count(db)
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "pending_count": pending_count,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/hr-confirmations/pending-count",
    response_model=ApiResponse[dict],
)
def pending_count_route(
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取待确认事项数量。"""
    count = get_pending_count(db)
    return {
        "success": True,
        "data": {"pending_count": count},
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/hr-confirmations/{item_id}",
    response_model=ApiResponse[ConfirmationItemResponse],
)
def get_hr_confirmation_route(
    item_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取确认事项详情。"""
    result = get_confirmation_item(db, item_id)
    if result is None:
        raise ResourceNotFound(f"确认事项不存在: {item_id}")
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/hr-confirmations/{item_id}/confirm",
    response_model=ApiResponse[ConfirmationItemResponse],
)
def confirm_hr_confirmation_route(
    item_id: int,
    body: ConfirmActionRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """确认处理。"""
    result = confirm_item(db, item_id, current_user, note=body.note, action_data=body.action_data)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="HR_CONFIRMATION",
        object_id=str(item_id),
        operation_type="HR_CONFIRM",
        after_data={"note": body.note},
        business_id=item_id,
    )
    db.commit()
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/hr-confirmations/{item_id}/reject",
    response_model=ApiResponse[ConfirmationItemResponse],
)
def reject_hr_confirmation_route(
    item_id: int,
    body: ConfirmActionRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """驳回处理。"""
    result = reject_item(db, item_id, current_user, note=body.note)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="HR_CONFIRMATION",
        object_id=str(item_id),
        operation_type="HR_REJECT",
        after_data={"note": body.note},
        business_id=item_id,
    )
    db.commit()
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/hr-confirmations/{item_id}/ignore",
    response_model=ApiResponse[ConfirmationItemResponse],
)
def ignore_hr_confirmation_route(
    item_id: int,
    body: ConfirmActionRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """忽略处理。"""
    result = ignore_item(db, item_id, current_user, note=body.note)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="HR_CONFIRMATION",
        object_id=str(item_id),
        operation_type="HR_IGNORE",
        after_data={"note": body.note},
        business_id=item_id,
    )
    db.commit()
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }

"""异动路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.change import (
    EmploymentChangeCreate,
    EmploymentChangeListResponse,
    EmploymentChangeResponse,
    EmploymentChangeUpdate,
)
from ..schemas.common import ApiResponse
from ..services.change_service import (
    create_change,
    get_change,
    list_changes,
    update_change,
)

router = APIRouter(tags=["异动"])


@router.get(
    "/employments/{employment_id}/changes",
    response_model=ApiResponse[EmploymentChangeListResponse],
)
def list_employment_changes_route(
    employment_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取任职的异动记录列表。"""
    items = list_changes(db, employment_id)
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items),
        },
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/changes",
    response_model=ApiResponse[EmploymentChangeResponse],
    status_code=201,
)
def create_employment_change_route(
    employment_id: int,
    body: EmploymentChangeCreate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建异动记录。"""
    result = create_change(db, employment_id, body.model_dump(), current_user)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employment-changes/{change_id}",
    response_model=ApiResponse[EmploymentChangeResponse],
)
def get_employment_change_route(
    change_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取异动详情。"""
    result = get_change(db, change_id)
    if result is None:
        raise ResourceNotFound(f"异动记录不存在: {change_id}")
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.patch(
    "/employment-changes/{change_id}",
    response_model=ApiResponse[EmploymentChangeResponse],
)
def update_employment_change_route(
    change_id: int,
    body: EmploymentChangeUpdate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新异动记录。"""
    result = update_change(db, change_id, body.model_dump(exclude_unset=True), current_user)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }

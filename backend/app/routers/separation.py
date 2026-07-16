"""离职路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..schemas.common import ApiResponse
from ..schemas.separation import (
    SeparationConfirm,
    SeparationPreviewResponse,
    SeparationRecordListResponse,
    SeparationRecordResponse,
    SeparationStart,
)
from ..services.separation_service import (
    confirm_separation,
    get_records,
    preview_separation,
    start_separation,
)
from ..services.operation_log_service import create_log

router = APIRouter(tags=["离职"])


@router.post(
    "/employments/{employment_id}/separation-preview",
    response_model=ApiResponse[SeparationPreviewResponse],
)
def preview_separation_route(
    employment_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """离职预览。"""
    result = preview_separation(db, employment_id)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/start-separation",
    response_model=ApiResponse[SeparationRecordResponse],
)
def start_separation_route(
    employment_id: int,
    body: SeparationStart,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """启动离职流程。"""
    result = start_separation(db, employment_id, body.model_dump(), current_user)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="SEPARATION",
        object_id=result.get("id"),
        operation_type="START",
        after_data={"employment_id": employment_id, "separation_type": result.get("separation_type")},
        business_id=employment_id,
    )
    db.commit()
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/confirm-separation",
    response_model=ApiResponse[SeparationRecordResponse],
)
def confirm_separation_route(
    employment_id: int,
    body: SeparationConfirm,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """确认离职。"""
    result = confirm_separation(db, employment_id, body.model_dump(), current_user)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="SEPARATION",
        object_id=result.get("id"),
        operation_type="CONFIRM",
        after_data={"employment_id": employment_id, "actual_separation_date": str(result.get("actual_separation_date", ""))},
        business_id=employment_id,
    )
    db.commit()
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employments/{employment_id}/separation-records",
    response_model=ApiResponse[SeparationRecordListResponse],
)
def list_separation_records_route(
    employment_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取离职记录列表。"""
    items = get_records(db, employment_id)
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items),
        },
        "request_id": str(uuid.uuid4()),
    }

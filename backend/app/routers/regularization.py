"""转正路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..schemas.common import ApiResponse
from ..schemas.regularization import (
    RegularizationConfirm,
    RegularizationPreviewResponse,
    RegularizationRecordListResponse,
    RegularizationRecordResponse,
)
from ..services.regularization_service import (
    confirm_regularization,
    get_records,
    preview_regularization,
)
from ..services.operation_log_service import create_log

router = APIRouter(tags=["转正"])


@router.post(
    "/employments/{employment_id}/regularization-preview",
    response_model=ApiResponse[RegularizationPreviewResponse],
)
def preview_regularization_route(
    employment_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """转正前预览。"""
    result = preview_regularization(db, employment_id)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/regularize",
    response_model=ApiResponse[RegularizationRecordResponse],
)
def confirm_regularization_route(
    employment_id: int,
    body: RegularizationConfirm,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """转正确认。"""
    result = confirm_regularization(db, employment_id, body.model_dump(), current_user)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="REGULARIZATION",
        object_id=result.get("id"),
        operation_type="CONFIRM",
        after_data={"decision": result.get("decision"), "employment_id": employment_id},
        business_id=employment_id,
    )
    db.commit()
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employments/{employment_id}/regularization-records",
    response_model=ApiResponse[RegularizationRecordListResponse],
)
def list_regularization_records_route(
    employment_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取转正记录列表。"""
    items = get_records(db, employment_id)
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items),
        },
        "request_id": str(uuid.uuid4()),
    }

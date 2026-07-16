"""试用期评估路由"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.common import ApiResponse
from ..schemas.probation import (
    ProbationReviewComplete,
    ProbationReviewCreate,
    ProbationReviewListResponse,
    ProbationReviewResponse,
    ProbationReviewUpdate,
)
from ..services.probation_service import (
    complete_review,
    create_review,
    get_review,
    list_reviews,
    update_review,
)
from ..services.operation_log_service import create_log

router = APIRouter(tags=["试用期评估"])


@router.get(
    "/employments/{employment_id}/probation-reviews",
    response_model=ApiResponse[ProbationReviewListResponse],
)
def list_probation_reviews_route(
    employment_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取任职的试用期评估列表。"""
    items = list_reviews(db, employment_id)
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items),
        },
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/probation-reviews",
    response_model=ApiResponse[ProbationReviewResponse],
    status_code=201,
)
def create_probation_review_route(
    employment_id: int,
    body: ProbationReviewCreate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建试用期评估。"""
    data = body.model_dump()
    data["employment_id"] = employment_id
    result = create_review(db, data, current_user)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="PROBATION_REVIEW",
        object_id=result.get("id"),
        operation_type="CREATE",
        after_data={"employment_id": employment_id, "review_stage": result.get("review_stage")},
        business_id=employment_id,
    )
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/probation-reviews/{review_id}",
    response_model=ApiResponse[ProbationReviewResponse],
)
def get_probation_review_route(
    review_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取试用期评估详情。"""
    result = get_review(db, review_id)
    if result is None:
        raise ResourceNotFound(f"试用期评估不存在: {review_id}")
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.patch(
    "/probation-reviews/{review_id}",
    response_model=ApiResponse[ProbationReviewResponse],
)
def update_probation_review_route(
    review_id: int,
    body: ProbationReviewUpdate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新试用期评估。"""
    result = update_review(db, review_id, body.model_dump(exclude_unset=True), current_user)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/probation-reviews/{review_id}/complete",
    response_model=ApiResponse[ProbationReviewResponse],
)
def complete_probation_review_route(
    review_id: int,
    body: ProbationReviewComplete,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """完成试用期评估。"""
    result = complete_review(db, review_id, body.model_dump(exclude_unset=True), current_user)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="PROBATION_REVIEW",
        object_id=review_id,
        operation_type="COMPLETE",
        after_data=result,
    )
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }

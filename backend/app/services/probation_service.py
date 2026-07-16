from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from ..enums import ProbationStatus, EmploymentStatus, OperationObjectType
from ..exceptions import (
    ResourceNotFound,
    InvalidStateTransition,
    Conflict,
)
from ..models import ProbationReview, EmploymentRecord
from .operation_log_service import create_log


def _to_dict(model: ProbationReview) -> dict[str, Any]:
    """将模型转为字典，过滤 None 值以外的字段。"""
    return model.dict()


def _check_employment_active(db: DBSession, employment_id: int) -> EmploymentRecord:
    """检查任职存在且未删除。"""
    emp = db.query(EmploymentRecord).filter(
        EmploymentRecord.id == employment_id,
        EmploymentRecord.is_deleted == False,
    ).first()
    if not emp:
        raise ResourceNotFound(f"任职记录不存在: {employment_id}")
    return emp


def create_review(db: DBSession, data: dict[str, Any], operator: dict[str, str]) -> dict[str, Any]:
    """创建试用期评估。"""
    employment = _check_employment_active(db, data["employment_id"])

    # 计算 review_seq
    max_seq = db.query(func.max(ProbationReview.review_seq)).filter(
        ProbationReview.employment_id == employment.id,
        ProbationReview.is_deleted == False,
    ).scalar()
    review_seq = (max_seq or 0) + 1

    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    review = ProbationReview(
        employment_id=employment.id,
        followup_task_id=data.get("followup_task_id"),
        communication_id=data.get("communication_id"),
        review_seq=review_seq,
        review_stage=data["review_stage"].value if hasattr(data["review_stage"], "value") else data["review_stage"],
        hr_evaluation=data.get("hr_evaluation"),
        employee_feedback=data.get("employee_feedback"),
        recommendation=data.get("recommendation"),
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(review)
    db.flush()

    # 更新任职试用期评估状态
    if employment.probation_status == ProbationStatus.IN_PROGRESS:
        employment.probation_status = ProbationStatus.PENDING_REVIEW
        employment.updated_by = operator_id

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.PROBATION_REVIEW.value,
        object_id=str(review.id),
        operation_type="CREATE",
        after_data=json.dumps({"review_seq": review_seq, "review_stage": review.review_stage}, ensure_ascii=False),
        business_id=employment.id,
    )

    db.flush()
    return _to_dict(review)


def update_review(db: DBSession, review_id: int, data: dict[str, Any], operator: dict[str, str]) -> dict[str, Any]:
    """更新试用期评估。"""
    review = db.query(ProbationReview).filter(
        ProbationReview.id == review_id,
        ProbationReview.is_deleted == False,
    ).first()
    if not review:
        raise ResourceNotFound(f"试用期评估不存在: {review_id}")

    if review.review_status is not None:
        raise InvalidStateTransition("已完成的评估不可修改")

    before = _to_dict(review)
    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    update_fields = ["hr_evaluation", "employee_feedback", "recommendation"]
    for field in update_fields:
        if field in data and data[field] is not None:
            setattr(review, field, data[field])

    review.updated_by = operator_id
    review.updated_at = now

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.PROBATION_REVIEW.value,
        object_id=str(review.id),
        operation_type="UPDATE",
        before_data=json.dumps(before, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(review), default=str, ensure_ascii=False),
        business_id=review.employment_id,
    )

    db.flush()
    return _to_dict(review)


def complete_review(db: DBSession, review_id: int, data: dict[str, Any], operator: dict[str, str]) -> dict[str, Any]:
    """完成试用期评估。"""
    review = db.query(ProbationReview).filter(
        ProbationReview.id == review_id,
        ProbationReview.is_deleted == False,
    ).first()
    if not review:
        raise ResourceNotFound(f"试用期评估不存在: {review_id}")

    if review.review_status is not None:
        raise InvalidStateTransition("评估已完成，不可重复完成")

    before = _to_dict(review)
    now = datetime.now()
    operator_id = operator.get("user_id", "system")

    review.review_status = data["review_status"]
    if data.get("hr_evaluation") is not None:
        review.hr_evaluation = data["hr_evaluation"]
    if data.get("employee_feedback") is not None:
        review.employee_feedback = data["employee_feedback"]
    if data.get("recommendation") is not None:
        review.recommendation = data["recommendation"]
    review.reviewed_by = operator_id
    review.reviewed_at = now
    review.updated_by = operator_id
    review.updated_at = now

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.PROBATION_REVIEW.value,
        object_id=str(review.id),
        operation_type="COMPLETE",
        before_data=json.dumps(before, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(review), default=str, ensure_ascii=False),
        business_id=review.employment_id,
    )

    db.flush()
    return _to_dict(review)


def get_review(db: DBSession, review_id: int) -> Optional[dict[str, Any]]:
    """获取试用期评估详情。"""
    review = db.query(ProbationReview).filter(
        ProbationReview.id == review_id,
        ProbationReview.is_deleted == False,
    ).first()
    if not review:
        return None
    return _to_dict(review)


def list_reviews(db: DBSession, employment_id: int) -> list[dict[str, Any]]:
    """获取任职的试用期评估列表。"""
    reviews = db.query(ProbationReview).filter(
        ProbationReview.employment_id == employment_id,
        ProbationReview.is_deleted == False,
    ).order_by(ProbationReview.review_seq.asc()).all()
    return [_to_dict(r) for r in reviews]

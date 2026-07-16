"""任职相关路由。"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.common import ApiResponse
from ..schemas.employment import (
    DateChangePreviewResponse,
    EmploymentCreate,
    EmploymentListResponse,
    EmploymentResponse,
    EmploymentUpdate,
)
from ..services.employment_service import (
    confirm_date_change,
    create_employment,
    get_employment,
    list_employee_employments,
    preview_date_change,
    update_employment,
)
from ..services.followup_service import generate_auto_tasks
from ..services.operation_log_service import create_log

router = APIRouter(tags=["任职"])


@router.get(
    "/employees/{employee_id}/employments",
    response_model=ApiResponse[EmploymentListResponse],
)
def list_employee_employments_route(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """查询员工任职记录列表。"""
    items, total = list_employee_employments(db, employee_id)
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employees/{employee_id}/employments",
    response_model=ApiResponse[EmploymentResponse],
)
def create_employment_route(
    employee_id: int,
    body: EmploymentCreate,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建员工任职记录，并自动生成跟进任务。"""
    # 确保路径中的 employee_id 与 body 一致
    data = body.model_dump()
    data["employee_id"] = employee_id
    rec = create_employment(db, data, current_user)

    # 自动生成跟进任务（幂等）
    generate_auto_tasks(db, rec["id"], rec["hire_date"])

    # 操作日志
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYMENT",
        object_id=rec["id"],
        operation_type="CREATE",
        after_data=rec,
        business_id=rec["employee_id"],
    )

    db.commit()
    return {
        "success": True,
        "data": rec,
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employments/{employment_id}",
    response_model=ApiResponse[EmploymentResponse],
)
def get_employment_route(
    employment_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """任职详情。"""
    rec = get_employment(db, employment_id)
    if not rec:
        raise ResourceNotFound("任职记录不存在")
    return {
        "success": True,
        "data": rec,
        "request_id": str(uuid.uuid4()),
    }


@router.patch(
    "/employments/{employment_id}",
    response_model=ApiResponse[EmploymentResponse],
)
def update_employment_route(
    employment_id: int,
    body: EmploymentUpdate,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新任职信息（部门 / 岗位 / 直属负责人）。"""
    old_rec = get_employment(db, employment_id)
    rec = update_employment(
        db, employment_id, body.model_dump(exclude_unset=True), current_user
    )

    # 操作日志
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYMENT",
        object_id=employment_id,
        operation_type="UPDATE",
        before_data=old_rec,
        after_data=rec,
        business_id=rec.get("employee_id"),
    )

    db.commit()
    return {
        "success": True,
        "data": rec,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/recalculate-followups",
)
def recalculate_followups_route(
    employment_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """手动触发跟进任务生成（幂等）。"""
    rec = get_employment(db, employment_id)
    if not rec:
        raise ResourceNotFound("任职记录不存在")
    tasks = generate_auto_tasks(db, rec["id"], rec["hire_date"])
    db.commit()
    return {
        "success": True,
        "data": tasks,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/date-change-preview",
    response_model=ApiResponse[DateChangePreviewResponse],
)
def preview_date_change_route(
    employment_id: int,
    new_hire_date: date = Body(..., embed=True, description="新入职日期"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """入职日期修改预览。"""
    preview = preview_date_change(db, employment_id, new_hire_date)
    return {
        "success": True,
        "data": preview,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employments/{employment_id}/date-change-confirm",
    response_model=ApiResponse[EmploymentResponse],
)
def confirm_date_change_route(
    employment_id: int,
    new_hire_date: date = Body(..., embed=True, description="新入职日期"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """确认修改入职日期（同一事务更新任职和任务）。"""
    old_rec = get_employment(db, employment_id)
    rec = confirm_date_change(db, employment_id, new_hire_date, current_user)

    # 操作日志
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYMENT",
        object_id=employment_id,
        operation_type="DATE_CHANGE",
        before_data=old_rec,
        after_data={"new_hire_date": str(new_hire_date)},
        business_id=rec.get("employee_id"),
    )

    db.commit()
    return {
        "success": True,
        "data": rec,
        "request_id": str(uuid.uuid4()),
    }

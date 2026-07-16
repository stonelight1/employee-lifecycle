"""员工相关路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.common import ApiResponse, PageParams
from ..schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from ..services.employee_service import (
    create_employee,
    delete_employee,
    get_employee,
    get_employee_timeline,
    list_employees,
    update_employee,
)
from ..services.operation_log_service import create_log

router = APIRouter(tags=["员工"])


@router.get("/employees", response_model=ApiResponse[dict])
def list_employees_route(
    params: PageParams = Depends(),
    keyword: str | None = Query(default=None, description="关键词搜索（姓名/编号/手机号/部门/岗位）"),
    name: str | None = Query(default=None, description="按姓名筛选"),
    employee_no: str | None = Query(default=None, description="按编号筛选"),
    employee_status: str | None = Query(default=None, description="按状态筛选"),
    lifecycle_stage: str | None = Query(default=None, description="生命周期阶段：PENDING/PROBATION/REGULARIZATION_PENDING/ACTIVE/SEPARATING/SEPARATED"),
    risk_level: str | None = Query(default=None, description="风险等级：NONE/LOW/MEDIUM/HIGH"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """员工列表（分页，聚合返回任职、风险、下一事项）。"""
    filters = {
        "keyword": keyword,
        "name": name,
        "employee_no": employee_no,
        "employee_status": employee_status,
        "lifecycle_stage": lifecycle_stage,
        "risk_level": risk_level,
        "page": params.page,
        "page_size": params.page_size,
        "sort_by": params.sort_by,
        "sort_order": params.sort_order,
    }
    items, total = list_employees(db, filters)

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.post("/employees", response_model=ApiResponse[EmployeeResponse])
def create_employee_route(
    body: EmployeeCreate,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建员工。"""
    emp = create_employee(db, body.model_dump(), current_user)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYEE",
        object_id=emp["id"],
        operation_type="CREATE",
        after_data=emp,
    )

    db.commit()
    return {
        "success": True,
        "data": emp,
        "request_id": str(uuid.uuid4()),
    }


@router.get("/employees/{employee_id}", response_model=ApiResponse[EmployeeResponse])
def get_employee_route(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """员工详情。"""
    emp = get_employee(db, employee_id)
    if not emp:
        raise ResourceNotFound("员工不存在")
    return {
        "success": True,
        "data": emp,
        "request_id": str(uuid.uuid4()),
    }


@router.patch("/employees/{employee_id}", response_model=ApiResponse[EmployeeResponse])
def update_employee_route(
    employee_id: int,
    body: EmployeeUpdate,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新员工信息。"""
    old_emp = get_employee(db, employee_id)
    emp = update_employee(db, employee_id, body.model_dump(exclude_unset=True), current_user)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYEE",
        object_id=employee_id,
        operation_type="UPDATE",
        before_data=old_emp,
        after_data=emp,
    )

    db.commit()
    return {
        "success": True,
        "data": emp,
        "request_id": str(uuid.uuid4()),
    }


@router.delete("/employees/{employee_id}", response_model=ApiResponse[dict])
def delete_employee_route(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """逻辑删除员工。"""
    old_emp = get_employee(db, employee_id)
    delete_employee(db, employee_id, current_user)

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYEE",
        object_id=employee_id,
        operation_type="DELETE",
        before_data=old_emp,
    )

    db.commit()
    return {
        "success": True,
        "data": {"deleted": True},
        "request_id": str(uuid.uuid4()),
    }


@router.get("/employees/{employee_id}/timeline", response_model=ApiResponse[dict])
def get_employee_timeline_route(
    employee_id: int,
    limit: int | None = Query(default=10, ge=1, le=100, description="返回事件数量"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """员工时间线（后端统一聚合所有事件类型）。"""
    result = get_employee_timeline(db, employee_id, limit=limit or 10)
    return {
        "success": True,
        "data": result,
        "request_id": str(uuid.uuid4()),
    }

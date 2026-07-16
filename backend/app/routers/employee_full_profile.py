"""员工完整档案和扩展信息路由。"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db_session
from ..enums import EmployeeStatus, FollowupTaskStatus, TodoStatus

logger = logging.getLogger(__name__)
from ..exceptions import Conflict
from ..models import (
    CompensationRecord,
    EmployeeAssessment,
    EmployeeAttributeHistory,
    EmployeeFinancialAccount,
    EmployeeNote,
    EmployeeProfile,
    EmploymentContract,
    EmploymentRecord,
    FollowupTask,
    SystemTodo,
)
from ..schemas.common import ApiResponse
from ..schemas.employee_profile import (
    AssessmentResponse,
    AttributeHistoryItem,
    CompensationResponse,
    ContractResponse,
    EmployeeProfileResponse,
    FinancialAccountResponse,
    FullProfileResponse,
    NoteResponse,
)
from ..services.employee_service import _get_active_employee
from ..services.operation_log_service import create_log

router = APIRouter(tags=["员工档案"])


# ── Pydantic schemas ──────────────────────────────────────────────


class ProfileUpdateRequest(BaseModel):
    """更新/创建员工扩展资料的请求体。"""

    identity_card: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_registration: Optional[str] = None
    residence_address: Optional[str] = None
    household_type: Optional[str] = None
    graduation_school: Optional[str] = None
    major: Optional[str] = None
    education_level: Optional[str] = None
    social_insurance_policy: Optional[str] = None
    housing_fund_policy: Optional[str] = None
    social_insurance_status: Optional[str] = None
    housing_fund_status: Optional[str] = None
    social_insurance_start_date: Optional[date] = None
    housing_fund_start_date: Optional[date] = None
    benefit_raw_text: Optional[str] = None


class MarkEntryErrorResponse(BaseModel):
    """标记入职错误的响应。"""

    employee: dict[str, Any]
    warning: Optional[str] = None


# ── 辅助函数 ─────────────────────────────────────────────────────


def _get_employments_for_employee(
    db: Session, employee_id: int
) -> list[EmploymentRecord]:
    """获取员工所有有效任职记录。"""
    return (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.desc())
        .all()
    )


def _get_employment_ids(employments: list[EmploymentRecord]) -> list[int]:
    """从任职记录列表中提取 ID 列表。"""
    return [e.id for e in employments]


def _has_business_records(
    db: Session, employee_id: int, employment_ids: list[int]
) -> bool:
    """检查员工是否存在业务记录（跟进任务、沟通记录、待办等）。"""
    if not employment_ids:
        return False

    # 跟进任务
    has_followup = (
        db.query(FollowupTask.id)
        .filter(
            FollowupTask.employment_id.in_(employment_ids),
            FollowupTask.is_deleted == False,
        )
        .first()
    )
    if has_followup:
        return True

    # 待办
    has_todo = (
        db.query(SystemTodo.id)
        .filter(
            SystemTodo.business_id.in_(employment_ids),
            SystemTodo.todo_status != TodoStatus.CANCELLED,
        )
        .first()
    )
    if has_todo:
        return True

    return False


def _cancel_pending_followups_and_todos(
    db: Session, employee_id: int, employment_ids: list[int]
) -> None:
    """取消所有待处理和进行中的跟进任务及待办。"""
    now = datetime.now()

    if employment_ids:
        # 取消跟进任务
        pending_followups = (
            db.query(FollowupTask)
            .filter(
                FollowupTask.employment_id.in_(employment_ids),
                FollowupTask.is_deleted == False,
                FollowupTask.followup_status.in_(
                    [FollowupTaskStatus.PENDING, FollowupTaskStatus.IN_PROGRESS]
                ),
            )
            .all()
        )
        for task in pending_followups:
            task.followup_status = FollowupTaskStatus.CANCELLED
            task.cancel_reason = "员工标记为入职错误，自动取消"
            task.updated_at = now

        # 取消待办
        pending_todos = (
            db.query(SystemTodo)
            .filter(
                SystemTodo.business_id.in_(employment_ids),
                SystemTodo.todo_status == TodoStatus.PENDING,
            )
            .all()
        )
        for todo in pending_todos:
            todo.todo_status = TodoStatus.CANCELLED
            todo.updated_at = now


# ── 端点 ─────────────────────────────────────────────────────────


@router.get(
    "/employees/{employee_id}/full-profile",
    response_model=ApiResponse[FullProfileResponse],
)
def get_full_profile(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工完整档案，包含所有扩展信息。"""
    emp = _get_active_employee(db, employee_id)
    emp_dict = emp.dict()

    # 扩展资料
    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.employee_id == employee_id)
        .first()
    )

    # 所有任职记录
    employments = _get_employments_for_employee(db, employee_id)
    employment_ids = _get_employment_ids(employments)

    # 当前任职（最新一条）
    current_employment = employments[0].dict() if employments else None

    # 合同
    contracts = (
        db.query(EmploymentContract)
        .filter(EmploymentContract.employee_id == employee_id)
        .order_by(desc(EmploymentContract.created_at))
        .all()
    )

    # 财务账户
    accounts = (
        db.query(EmployeeFinancialAccount)
        .filter(EmployeeFinancialAccount.employee_id == employee_id)
        .all()
    )

    # 薪酬记录（最新优先）
    compensations = (
        db.query(CompensationRecord)
        .filter(CompensationRecord.employee_id == employee_id)
        .order_by(desc(CompensationRecord.effective_date), desc(CompensationRecord.created_at))
        .all()
    )

    # 测评记录（最新优先）
    assessments = (
        db.query(EmployeeAssessment)
        .filter(EmployeeAssessment.employee_id == employee_id)
        .order_by(desc(EmployeeAssessment.created_at))
        .all()
    )

    # 备注（最新优先）
    notes = (
        db.query(EmployeeNote)
        .filter(EmployeeNote.employee_id == employee_id)
        .order_by(desc(EmployeeNote.created_at))
        .all()
    )

    # 属性变更历史（最新优先）
    attribute_history_query = (
        db.query(EmployeeAttributeHistory)
        .filter(EmployeeAttributeHistory.employee_id == employee_id)
        .order_by(desc(EmployeeAttributeHistory.created_at))
        .limit(100)
        .all()
    )
    attribute_history = []
    for h in attribute_history_query:
        item = h.dict()
        attribute_history.append(
            AttributeHistoryItem(
                id=item["id"],
                employee_id=item["employee_id"],
                field_name=item["field_name"],
                before_value=item.get("before_value_json"),
                after_value=item.get("after_value_json"),
                effective_date=item.get("effective_date"),
                source_type=item.get("source_type", ""),
                operator_name=item.get("operator_name"),
                created_at=item.get("created_at"),
            ).model_dump()
        )

    return {
        "success": True,
        "data": {
            "employee": emp_dict,
            "profile": EmployeeProfileResponse.model_validate(profile).model_dump() if profile else None,
            "current_employment": current_employment,
            "all_employments": [e.dict() for e in employments],
            "contracts": [ContractResponse.model_validate(c).model_dump() for c in contracts],
            "financial_accounts": [FinancialAccountResponse.model_validate(a).model_dump() for a in accounts],
            "compensations": [CompensationResponse.model_validate(c).model_dump() for c in compensations],
            "assessments": [AssessmentResponse.model_validate(a).model_dump() for a in assessments],
            "notes": [NoteResponse.model_validate(n).model_dump() for n in notes],
            "attribute_history": attribute_history,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/profile",
    response_model=ApiResponse[EmployeeProfileResponse],
)
def get_profile(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工扩展资料。不存在时返回空结构。"""
    _get_active_employee(db, employee_id)

    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.employee_id == employee_id)
        .first()
    )

    if profile:
        data = EmployeeProfileResponse.model_validate(profile).model_dump()
    else:
        data = EmployeeProfileResponse(employee_id=employee_id).model_dump()

    return {
        "success": True,
        "data": data,
        "request_id": str(uuid.uuid4()),
    }


@router.put(
    "/employees/{employee_id}/profile",
    response_model=ApiResponse[EmployeeProfileResponse],
)
def upsert_profile(
    employee_id: int,
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建或更新员工扩展资料。"""
    emp = _get_active_employee(db, employee_id)
    now = datetime.now()

    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.employee_id == employee_id)
        .first()
    )

    is_new = False
    if not profile:
        profile = EmployeeProfile(employee_id=employee_id)
        db.add(profile)
        is_new = True

    # 记录更新前的数据
    before_data = profile.dict() if not is_new else None

    # 更新字段
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.updated_at = now
    profile.updated_by = current_user.get("user_id", "system")

    if is_new:
        profile.created_by = current_user.get("user_id", "system")

    db.flush()
    after_data = profile.dict()

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYEE_PROFILE",
        object_id=employee_id,
        operation_type="CREATE" if is_new else "UPDATE",
        before_data=before_data,
        after_data=after_data,
        business_id=employee_id,
    )

    db.commit()
    return {
        "success": True,
        "data": EmployeeProfileResponse.model_validate(profile).model_dump(),
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/contracts",
    response_model=ApiResponse[list[ContractResponse]],
)
def list_contracts(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工合同列表。"""
    _get_active_employee(db, employee_id)

    contracts = (
        db.query(EmploymentContract)
        .filter(EmploymentContract.employee_id == employee_id)
        .order_by(desc(EmploymentContract.created_at))
        .all()
    )

    return {
        "success": True,
        "data": [ContractResponse.model_validate(c).model_dump() for c in contracts],
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/financial-accounts",
    response_model=ApiResponse[list[FinancialAccountResponse]],
)
def list_financial_accounts(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工财务账户列表。"""
    _get_active_employee(db, employee_id)

    accounts = (
        db.query(EmployeeFinancialAccount)
        .filter(EmployeeFinancialAccount.employee_id == employee_id)
        .all()
    )

    return {
        "success": True,
        "data": [FinancialAccountResponse.model_validate(a).model_dump() for a in accounts],
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/compensations",
    response_model=ApiResponse[list[CompensationResponse]],
)
def list_compensations(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工薪酬记录列表（最近优先）。"""
    _get_active_employee(db, employee_id)

    compensations = (
        db.query(CompensationRecord)
        .filter(CompensationRecord.employee_id == employee_id)
        .order_by(desc(CompensationRecord.effective_date), desc(CompensationRecord.created_at))
        .all()
    )

    return {
        "success": True,
        "data": [CompensationResponse.model_validate(c).model_dump() for c in compensations],
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/assessments",
    response_model=ApiResponse[list[AssessmentResponse]],
)
def list_assessments(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工测评记录列表（最近优先）。"""
    _get_active_employee(db, employee_id)

    assessments = (
        db.query(EmployeeAssessment)
        .filter(EmployeeAssessment.employee_id == employee_id)
        .order_by(desc(EmployeeAssessment.created_at))
        .all()
    )

    return {
        "success": True,
        "data": [AssessmentResponse.model_validate(a).model_dump() for a in assessments],
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/notes",
    response_model=ApiResponse[list[NoteResponse]],
)
def list_notes(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工备注列表（最近优先）。"""
    _get_active_employee(db, employee_id)

    notes = (
        db.query(EmployeeNote)
        .filter(EmployeeNote.employee_id == employee_id)
        .order_by(desc(EmployeeNote.created_at))
        .all()
    )

    return {
        "success": True,
        "data": [NoteResponse.model_validate(n).model_dump() for n in notes],
        "request_id": str(uuid.uuid4()),
    }


@router.get(
    "/employees/{employee_id}/attribute-history",
    response_model=ApiResponse[list[AttributeHistoryItem]],
)
def list_attribute_history(
    employee_id: int,
    category: Optional[str] = Query(default=None, description="按分类筛选"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取员工属性变更历史（最近优先）。"""
    _get_active_employee(db, employee_id)

    query = (
        db.query(EmployeeAttributeHistory)
        .filter(EmployeeAttributeHistory.employee_id == employee_id)
    )
    if category:
        query = query.filter(EmployeeAttributeHistory.category == category)

    history = (
        query.order_by(desc(EmployeeAttributeHistory.created_at))
        .limit(200)
        .all()
    )

    history_items = []
    for h in history:
        item = h.dict()
        history_items.append(
            AttributeHistoryItem(
                id=item["id"],
                employee_id=item["employee_id"],
                field_name=item["field_name"],
                before_value=item.get("before_value_json"),
                after_value=item.get("after_value_json"),
                effective_date=item.get("effective_date"),
                source_type=item.get("source_type", ""),
                operator_name=item.get("operator_name"),
                created_at=item.get("created_at"),
            ).model_dump()
        )

    return {
        "success": True,
        "data": history_items,
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employees/{employee_id}/mark-entry-error",
    response_model=ApiResponse[MarkEntryErrorResponse],
)
def mark_entry_error(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """将员工标记为入职错误。

    检查是否存在业务记录；如果存在则警告但仍允许操作。
    同时取消所有待处理和进行中的跟进任务及待办。
    """
    emp = _get_active_employee(db, employee_id)

    if emp.employee_status == EmployeeStatus.ENTRY_ERROR:
        raise Conflict("员工已标记为入职错误")

    # 检查业务记录
    employments = _get_employments_for_employee(db, employee_id)
    employment_ids = _get_employment_ids(employments)

    warning = None
    if _has_business_records(db, employee_id, employment_ids):
        warning = "员工存在业务记录（跟进任务、待办等），标记后相关业务数据将保留但关联任务将被取消"

    # 取消待处理的任务和待办
    _cancel_pending_followups_and_todos(db, employee_id, employment_ids)

    # 更新员工状态
    before_data = emp.dict()
    emp.employee_status = EmployeeStatus.ENTRY_ERROR

    db.flush()
    after_data = emp.dict()

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYEE",
        object_id=employee_id,
        operation_type="MARK_ENTRY_ERROR",
        before_data=before_data,
        after_data=after_data,
        business_id=employee_id,
    )

    db.commit()
    return {
        "success": True,
        "data": {
            "employee": after_data,
            "warning": warning,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.post(
    "/employees/{employee_id}/remove-entry-error",
    response_model=ApiResponse[MarkEntryErrorResponse],
)
def remove_entry_error(
    employee_id: int,
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """移除员工入职错误标记，恢复为正常状态。"""
    emp = _get_active_employee(db, employee_id)

    if emp.employee_status != EmployeeStatus.ENTRY_ERROR:
        raise Conflict("员工当前不是入职错误状态，无法移除标记")

    before_data = emp.dict()
    emp.employee_status = EmployeeStatus.ACTIVE

    db.flush()
    after_data = emp.dict()

    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="EMPLOYEE",
        object_id=employee_id,
        operation_type="REMOVE_ENTRY_ERROR",
        before_data=before_data,
        after_data=after_data,
        business_id=employee_id,
    )

    db.commit()
    return {
        "success": True,
        "data": {
            "employee": after_data,
            "warning": None,
        },
        "request_id": str(uuid.uuid4()),
    }

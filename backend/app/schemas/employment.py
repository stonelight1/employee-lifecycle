"""任职相关 Pydantic v2 schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import EmploymentStatus, EmploymentType, ProbationStatus, WorkMode


class EmploymentCreate(BaseModel):
    """创建任职请求。"""

    hire_date: date = Field(..., description="入职日期")
    probation_months: int = Field(default=3, ge=1, le=6, description="试用期月数(1-6)")
    department: Optional[str] = Field(default=None, max_length=200, description="部门")
    position: Optional[str] = Field(default=None, max_length=200, description="岗位")
    manager_name: Optional[str] = Field(default=None, max_length=100, description="直属负责人")
    employment_type: Optional[EmploymentType] = Field(default=None, description="员工类型")
    work_city: Optional[str] = Field(default=None, max_length=100, description="工作城市")
    work_mode: Optional[WorkMode] = Field(default=None, description="办公方式")
    team_name: Optional[str] = Field(default=None, max_length=200, description="分队")


class EmploymentUpdate(BaseModel):
    """更新任职请求（所有字段可选）。"""

    department: Optional[str] = Field(default=None, max_length=200)
    position: Optional[str] = Field(default=None, max_length=200)
    manager_name: Optional[str] = Field(default=None, max_length=100)
    team_name: Optional[str] = Field(default=None, max_length=200)
    work_city: Optional[str] = Field(default=None, max_length=100)
    work_mode: Optional[WorkMode] = Field(default=None)


class EmploymentResponse(BaseModel):
    """任职完整响应字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employment_seq: int
    employment_status: EmploymentStatus
    hire_date: date
    expected_hire_date: Optional[date] = None
    actual_hire_date: Optional[date] = None
    probation_months: int = 3
    probation_start_date: Optional[date] = None
    probation_end_date: Optional[date] = None
    expected_regularization_date: Optional[date] = None
    actual_regularization_date: Optional[date] = None
    probation_status: ProbationStatus
    employment_type: Optional[EmploymentType] = None
    work_city: Optional[str] = None
    work_mode: Optional[WorkMode] = None
    team_name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    manager_name: Optional[str] = None
    regularization_date: Optional[date] = None
    separation_date: Optional[date] = None
    status_before_separating: Optional[str] = None
    hire_cancelled_at: Optional[datetime] = None
    hire_cancel_reasons_json: Optional[str] = None
    hire_cancel_note: Optional[str] = None
    date_rule_source: Optional[str] = None
    probation_end_date_source: Optional[str] = None

    # CommonMixin 通用字段
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    version: int = 1
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None


class EmploymentListResponse(BaseModel):
    """员工任职列表响应。"""

    items: list[EmploymentResponse]
    total: int


class DateChangeTaskItem(BaseModel):
    """日期修改预览中的单个任务项。"""

    task_id: int
    task_name: str
    planned_date: Optional[date] = None
    new_planned_date: Optional[date] = None
    reason: Optional[str] = None


class DateChangePreviewResponse(BaseModel):
    """入职日期修改预览响应。"""

    old_hire_date: date
    new_hire_date: date
    old_probation_end_date: Optional[date] = None
    new_probation_end_date: Optional[date] = None
    recalculated_tasks: list[DateChangeTaskItem] = []
    not_modified_tasks: list[DateChangeTaskItem] = []

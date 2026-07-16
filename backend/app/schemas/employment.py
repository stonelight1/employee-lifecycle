"""任职相关 Pydantic v2 schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import EmploymentStatus, ProbationStatus


class EmploymentCreate(BaseModel):
    """创建任职请求。"""

    hire_date: date = Field(..., description="入职日期")
    department: Optional[str] = Field(default=None, max_length=200, description="部门")
    position: Optional[str] = Field(default=None, max_length=200, description="岗位")
    manager_name: Optional[str] = Field(default=None, max_length=100, description="直属负责人")


class EmploymentUpdate(BaseModel):
    """更新任职请求（所有字段可选）。"""

    department: Optional[str] = Field(default=None, max_length=200)
    position: Optional[str] = Field(default=None, max_length=200)
    manager_name: Optional[str] = Field(default=None, max_length=100)


class EmploymentResponse(BaseModel):
    """任职完整响应字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employment_seq: int
    employment_status: EmploymentStatus
    hire_date: date
    probation_start_date: Optional[date] = None
    probation_end_date: Optional[date] = None
    probation_status: ProbationStatus
    department: Optional[str] = None
    position: Optional[str] = None
    manager_name: Optional[str] = None
    regularization_date: Optional[date] = None
    separation_date: Optional[date] = None
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

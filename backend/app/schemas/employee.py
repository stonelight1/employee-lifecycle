"""员工相关 Pydantic v2 schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import EmployeeStatus


class EmployeeCreate(BaseModel):
    """创建员工请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="员工姓名")
    employee_no: Optional[str] = Field(default=None, max_length=50, description="员工编号")
    mobile: Optional[str] = Field(default=None, max_length=30, description="手机号")
    email: Optional[str] = Field(default=None, max_length=200, description="邮箱")
    source: Optional[str] = Field(default=None, max_length=100, description="来源")


class EmployeeUpdate(BaseModel):
    """更新员工请求（所有字段可选）。

    注意：姓名不允许通过普通更新接口修改。
    """

    employee_no: Optional[str] = Field(default=None, max_length=50)
    mobile: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=200)
    source: Optional[str] = Field(default=None, max_length=100)


class EmployeeResponse(BaseModel):
    """员工完整响应字段（与模型一致）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_no: Optional[str] = None
    name: str
    normalized_name: str
    mobile: Optional[str] = None
    email: Optional[str] = None
    source_employee_key: Optional[str] = None
    employee_status: EmployeeStatus
    source: Optional[str] = None

    # CommonMixin 通用字段
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    version: int = 1
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None


class EmployeeListResponse(BaseModel):
    """分页员工列表包装。"""

    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import ChangeType


class EmploymentChangeCreate(BaseModel):
    """创建异动请求"""
    change_type: ChangeType
    effective_date: date
    before_data: Optional[dict[str, Any]] = None
    after_data: Optional[dict[str, Any]] = None
    reason: Optional[str] = Field(None, max_length=500)


class EmploymentChangeUpdate(BaseModel):
    """更新异动请求"""
    effective_date: Optional[date] = None
    after_data: Optional[dict[str, Any]] = None
    reason: Optional[str] = Field(None, max_length=500)


class EmploymentChangeListResponse(BaseModel):
    """异动记录列表响应"""
    items: list[EmploymentChangeResponse]
    total: int


class EmploymentChangeResponse(BaseModel):
    """异动记录响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employment_id: int
    change_type: str
    effective_date: date
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    reason: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    version: int = 1
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

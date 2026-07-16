from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SeparationStart(BaseModel):
    """启动离职请求"""
    planned_separation_date: Optional[date] = None
    separation_type: Optional[str] = Field(None, max_length=50)
    reason: Optional[str] = None
    hr_comment: Optional[str] = None


class SeparationConfirm(BaseModel):
    """确认离职请求"""
    actual_separation_date: Optional[date] = None
    hr_comment: Optional[str] = None
    confirm: bool = True


class SeparationPreviewResponse(BaseModel):
    """离职预览响应"""
    employment_id: int
    employment_status: str
    hire_date: date
    probation_status: Optional[str] = None
    pending_tasks_count: int = 0
    pending_todos_count: int = 0
    can_start_separation: bool = True
    warnings: list[str] = []


class SeparationRecordListResponse(BaseModel):
    """离职记录列表响应"""
    items: list[SeparationRecordResponse]
    total: int


class SeparationRecordResponse(BaseModel):
    """离职记录响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employment_id: int
    planned_separation_date: Optional[date] = None
    actual_separation_date: Optional[date] = None
    separation_type: Optional[str] = None
    reason: Optional[str] = None
    hr_comment: Optional[str] = None
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

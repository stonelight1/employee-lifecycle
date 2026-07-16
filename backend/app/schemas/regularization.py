from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import RegularizationDecision


class RegularizationPreviewResponse(BaseModel):
    """转正前预览响应"""
    employment_id: int
    hire_date: date
    probation_start_date: Optional[date] = None
    probation_end_date: Optional[date] = None
    probation_status: str
    has_completed_final_review: bool
    final_review: Optional[dict] = None
    can_regularize: bool
    warnings: list[str] = []


class RegularizationConfirm(BaseModel):
    """转正确认请求"""
    decision: RegularizationDecision
    effective_date: Optional[date] = None
    new_probation_end_date: Optional[date] = None
    decision_reason: Optional[str] = None
    ai_summary_version_id: Optional[int] = None


class RegularizationRecordListResponse(BaseModel):
    """转正记录列表响应"""
    items: list[RegularizationRecordResponse]
    total: int


class RegularizationRecordResponse(BaseModel):
    """转正记录响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employment_id: int
    probation_review_id: Optional[int] = None
    decision: str
    effective_date: Optional[date] = None
    new_probation_end_date: Optional[date] = None
    decision_reason: Optional[str] = None
    ai_summary_version_id: Optional[int] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    is_effective: bool
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    version: int = 1
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

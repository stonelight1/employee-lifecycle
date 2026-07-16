from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import ReviewStage


class ProbationReviewCreate(BaseModel):
    """创建试用期评估请求"""
    employment_id: int
    followup_task_id: Optional[int] = None
    communication_id: Optional[int] = None
    review_stage: ReviewStage
    hr_evaluation: Optional[str] = None
    employee_feedback: Optional[str] = None
    recommendation: Optional[str] = Field(None, max_length=500)


class ProbationReviewUpdate(BaseModel):
    """更新试用期评估请求"""
    hr_evaluation: Optional[str] = None
    employee_feedback: Optional[str] = None
    recommendation: Optional[str] = Field(None, max_length=500)


class ProbationReviewComplete(BaseModel):
    """完成试用期评估请求"""
    review_status: str = Field(..., description="评估完成状态，如 COMPLETED")
    hr_evaluation: Optional[str] = None
    employee_feedback: Optional[str] = None
    recommendation: Optional[str] = Field(None, max_length=500)


class ProbationReviewListResponse(BaseModel):
    """试用期评估列表响应"""
    items: list[ProbationReviewResponse]
    total: int


class ProbationReviewResponse(BaseModel):
    """试用期评估响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employment_id: int
    followup_task_id: Optional[int] = None
    communication_id: Optional[int] = None
    review_seq: int
    review_stage: str
    review_status: Optional[str] = None
    hr_evaluation: Optional[str] = None
    employee_feedback: Optional[str] = None
    recommendation: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    version: int = 1
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

"""HR 确认事项相关 Pydantic v2 schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConfirmationItemResponse(BaseModel):
    """确认事项响应。"""
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    employment_id: Optional[int] = None
    source_type: str
    source_id: Optional[str] = None
    issue_code: str
    title: str
    description: Optional[str] = None
    before_data: Optional[Any] = None
    after_data: Optional[Any] = None
    item_status: str
    created_at: datetime
    handled_at: Optional[datetime] = None


class ConfirmationListResponse(BaseModel):
    """确认事项列表响应。"""
    items: list[ConfirmationItemResponse]
    total: int
    pending_count: int


class ConfirmActionRequest(BaseModel):
    """确认/拒绝/忽略操作的请求体。"""
    note: Optional[str] = Field(default=None, description="备注")
    action_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="业务动作数据，用于补充缺失字段等场景。"
        "例如 {\"actual_regularization_date\": \"2024-07-01\"}",
    )

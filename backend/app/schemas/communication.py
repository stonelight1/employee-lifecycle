"""
沟通管理 —— Pydantic v2 Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommunicationCreate(BaseModel):
    """创建沟通记录"""
    employment_id: int
    followup_task_id: Optional[int] = None
    communication_type: Optional[str] = None
    communication_at: Optional[datetime] = None
    communication_text: Optional[str] = None
    manual_summary: Optional[str] = None
    hr_conclusion: Optional[str] = None
    source: Optional[str] = None


class CommunicationUpdate(BaseModel):
    """更新沟通记录"""
    communication_at: Optional[datetime] = None
    communication_text: Optional[str] = None
    manual_summary: Optional[str] = None
    hr_conclusion: Optional[str] = None
    change_reason: Optional[str] = None
    version: Optional[int] = None


class CommunicationResponse(BaseModel):
    """沟通记录响应"""
    id: int
    employment_id: int
    followup_task_id: Optional[int] = None
    communication_type: Optional[str] = None
    communication_at: Optional[datetime] = None
    hr_user_id: Optional[str] = None
    communication_status: str
    current_text_version_id: Optional[int] = None
    current_text_version_no: Optional[int] = None
    current_text_hash: Optional[str] = None
    manual_summary: Optional[str] = None
    hr_conclusion: Optional[str] = None
    source: Optional[str] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 1

    model_config = {"from_attributes": True}


class CommunicationListResponse(BaseModel):
    """沟通记录列表响应"""
    items: list[CommunicationResponse]
    total: int


class TextVersionResponse(BaseModel):
    """沟通文本版本响应"""
    id: int
    communication_id: int
    version_no: int
    text_content: str
    text_hash: Optional[str] = None
    text_length: int = 0
    change_reason: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None

    model_config = {"from_attributes": True}

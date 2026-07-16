from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# === 待办 ===

class SystemTodoCreate(BaseModel):
    """内部创建待办请求"""
    user_id: str
    business_type: str
    business_id: int
    title: str
    due_at: Optional[date] = None
    priority: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=50)
    idempotency_key: Optional[str] = Field(None, max_length=200)


class SystemTodoResponse(BaseModel):
    """待办响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    business_type: str
    business_id: int
    title: str
    due_at: Optional[date] = None
    todo_status: str
    priority: Optional[str] = None
    source: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    version: Optional[int] = None


class TodoCompleteRequest(BaseModel):
    """完成待办请求"""
    pass


class TodoCancelRequest(BaseModel):
    """取消待办请求"""
    reason: str = Field(..., max_length=500)


# === 操作日志 ===

class OperationLogResponse(BaseModel):
    """操作日志响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    operator_id: str
    operated_at: datetime
    object_type: str
    object_id: str
    operation_type: str
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    operation_source: Optional[str] = None
    business_id: Optional[int] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class TodoListResponse(BaseModel):
    """待办列表响应"""
    items: list[SystemTodoResponse]
    total: int
    page: int
    page_size: int


class OperationLogListResponse(BaseModel):
    """操作日志列表响应"""
    items: list[OperationLogResponse]
    total: int
    page: int
    page_size: int

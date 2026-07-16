"""
跟进节点和任务 Pydantic v2 Schemas。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..enums import (
    ConfirmationMode,
    ConfirmationStatus,
    FollowupTaskStatus,
    ParticipantRole,
    TaskSource,
    TriggerType,
)


def _request_id() -> str:
    return uuid.uuid4().hex[:16]


# ============================================================
# FollowupNode
# ============================================================


class FollowupNodeCreate(BaseModel):
    node_code: str = Field(..., max_length=50, description="节点业务编码")
    node_name: str = Field(..., max_length=200, description="节点名称")
    trigger_type: TriggerType = Field(
        default=TriggerType.DAYS_AFTER_HIRE, description="触发类型"
    )
    offset_days: Optional[int] = Field(default=None, ge=0, description="偏移天数")
    confirmation_mode: ConfirmationMode = Field(
        default=ConfirmationMode.ALL, description="确认模式"
    )
    default_assignee_rule: Optional[str] = Field(
        default=None, max_length=200, description="默认负责人规则"
    )
    effective_from: Optional[date] = Field(default=None, description="生效开始日期")
    effective_to: Optional[date] = Field(default=None, description="生效结束日期")


class FollowupNodeUpdate(BaseModel):
    node_name: Optional[str] = Field(default=None, max_length=200)
    offset_days: Optional[int] = Field(default=None, ge=0)
    confirmation_mode: Optional[ConfirmationMode] = Field(default=None)
    default_assignee_rule: Optional[str] = Field(default=None, max_length=200)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)


class FollowupNodeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    node_code: str
    node_name: str
    trigger_type: str
    offset_days: Optional[int] = None
    enabled: bool
    default_assignee_rule: Optional[str] = None
    confirmation_mode: str
    node_version: int
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


# ============================================================
# FollowupTask
# ============================================================


class FollowupTaskCreate(BaseModel):
    """手工创建任务时使用的请求体。"""

    employment_id: int = Field(..., description="任职记录 ID")
    task_name: str = Field(..., max_length=200, description="任务名称")
    planned_date: date = Field(..., description="计划日期")
    confirmation_mode: ConfirmationMode = Field(
        default=ConfirmationMode.ALL, description="确认模式"
    )
    request_id: Optional[str] = Field(
        default=None, max_length=200, description="幂等键（可选）"
    )


class FollowupTaskUpdate(BaseModel):
    followup_status: Optional[FollowupTaskStatus] = Field(default=None)
    planned_date: Optional[date] = Field(default=None, description="计划日期")
    date_adjusted_manually: Optional[bool] = Field(default=None)


class _TaskParticipantItem(BaseModel):
    """参与人信息。"""

    user_id: str = Field(..., description="用户 ID")
    participant_role: ParticipantRole = Field(
        default=ParticipantRole.PARTICIPANT, description="参与角色"
    )
    active: bool = True
    assigned_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None


class _TaskConfirmationItem(BaseModel):
    """确认记录。"""

    user_id: str = Field(..., description="用户 ID")
    confirmation_status: ConfirmationStatus = Field(
        default=ConfirmationStatus.PENDING, description="确认状态"
    )
    comment: Optional[str] = Field(default=None)
    confirmed_at: Optional[datetime] = Field(default=None)


class FollowupTaskResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    employment_id: int
    node_definition_id: Optional[int] = None
    node_version: Optional[int] = None
    node_code_snapshot: Optional[str] = None
    task_name: str
    task_source: str
    trigger_type_snapshot: Optional[str] = None
    offset_days_snapshot: Optional[int] = None
    planned_date: date
    original_planned_date: Optional[date] = None
    date_adjusted_manually: bool = False
    followup_status: str
    confirmation_mode: str
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    cancel_reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    # 关联数据（非持久化字段，由 service 层填充）
    participants: list[_TaskParticipantItem] = Field(default_factory=list)
    confirmations: list[_TaskConfirmationItem] = Field(default_factory=list)


class FollowupTaskListResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    employment_id: int
    node_code_snapshot: Optional[str] = None
    task_name: str
    task_source: str
    planned_date: date
    followup_status: str
    confirmation_mode: str
    date_adjusted_manually: bool = False
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    participant_count: int = 0


# ============================================================
# 参与人 / 确认 / 取消 请求
# ============================================================


class TaskParticipantAdd(BaseModel):
    user_id: str = Field(..., max_length=100, description="用户 ID")
    participant_role: ParticipantRole = Field(
        default=ParticipantRole.PARTICIPANT, description="参与角色"
    )


class TaskConfirmRequest(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=1000, description="确认备注")


class TaskCancelRequest(BaseModel):
    reason: str = Field(..., max_length=500, description="取消原因")


# ============================================================
# 通用业务响应包装
# ============================================================


class ApiResponse(BaseModel):
    """通用业务响应。"""

    model_config = {"arbitrary_types_allowed": True}

    success: bool = True
    data: object = None
    request_id: str = Field(default_factory=_request_id)


def api_success(data: object = None, request_id: str | None = None) -> dict:
    """构建统一成功响应。"""
    return {
        "success": True,
        "data": data,
        "request_id": request_id or _request_id(),
    }

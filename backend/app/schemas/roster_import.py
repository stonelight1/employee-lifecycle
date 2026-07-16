"""花名册导入相关 Pydantic v2 schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# 上传
# ============================================================

class RosterUploadResponse(BaseModel):
    """上传响应。"""
    batch_id: int
    batch_no: str
    file_name: str
    file_size: int
    file_sha256: str
    sheet_names: list[str] = []
    selected_sheet: Optional[str] = None
    header_row: int = 1
    total_rows: int = 0
    status: str
    message: str = ""
    suggestion: Optional[str] = None


# ============================================================
# 字段映射
# ============================================================

class ColumnMapping(BaseModel):
    """单列映射。"""
    source_header: str = Field(..., description="Excel 列名")
    source_header_normalized: str = Field(..., description="标准化列名")
    target_field_key: Optional[str] = Field(default=None, description="映射到的系统字段")
    is_mapped: bool = False
    is_required: bool = False
    is_unknown: bool = False
    save_as_alias: bool = False


class FieldDefinition(BaseModel):
    """系统字段定义。"""
    key: str
    label: str
    required: bool = False
    description: str = ""
    example_values: str = ""


class SaveMappingRequest(BaseModel):
    """保存映射请求。"""
    mappings: dict[str, Optional[str]] = Field(..., description="Excel列名 -> 系统字段")


class SaveMappingResponse(BaseModel):
    """保存映射响应。"""
    batch_id: int
    mapped_count: int
    unmapped_count: int
    unmapped_required: list[str] = []


# ============================================================
# 预览
# ============================================================

class RowPreviewItem(BaseModel):
    """单行预览数据。"""
    row_no: int
    employee_id: Optional[int] = None
    normalized_name: Optional[str] = None
    matched_employee_name: Optional[str] = None
    row_status: str
    diff_fields: list[dict] = []
    issues: list[dict] = []
    can_skip: bool = True
    actions: list[str] = []


class PreviewSummary(BaseModel):
    """导入预览汇总。"""
    new_count: int = 0
    update_count: int = 0
    unchanged_count: int = 0
    confirmation_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    blocker_count: int = 0
    warning_count: int = 0
    total_rows: int = 0


class PreviewResponse(BaseModel):
    """预览响应。"""
    batch_id: int
    mode: str
    summary: PreviewSummary
    rows: list[RowPreviewItem] = []
    field_definitions: list[FieldDefinition] = []
    current_mappings: dict[str, str] = {}


# ============================================================
# 问题处理
# ============================================================

class IssueItem(BaseModel):
    """导入问题项。"""
    id: int
    row_id: Optional[int] = None
    employee_id: Optional[int] = None
    field_key: Optional[str] = None
    issue_code: str
    severity: str
    title: str
    message: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    allowed_actions: list[str] = []
    resolution_status: str = "PENDING"
    row_no: Optional[int] = None
    employee_name: Optional[str] = None


class ResolveIssueRequest(BaseModel):
    """处理问题请求。"""
    action: str = Field(..., description="操作")
    value: Optional[Any] = Field(default=None, description="处理值")
    note: Optional[str] = Field(default=None, description="备注")


# ============================================================
# 提交
# ============================================================

class CommitConfirmation(BaseModel):
    """提交确认信息。"""
    will_create: int = 0
    will_update: int = 0
    will_create_changes: int = 0
    will_create_compensations: int = 0
    will_create_notes: int = 0
    will_create_confirmations: int = 0
    will_skip: int = 0


class CommitResponse(BaseModel):
    """提交响应。"""
    batch_id: int
    batch_no: str
    status: str
    message: str
    summary: Optional[PreviewSummary] = None


# ============================================================
# 导入历史
# ============================================================

class BatchListItem(BaseModel):
    """导入批次列表项。"""
    id: int
    batch_no: str
    mode: str
    file_name: str
    file_sha256: str
    batch_status: str
    total_rows: int
    new_count: int
    update_count: int
    skipped_count: int
    confirmation_count: int
    error_count: int
    warning_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None


class BatchListResponse(BaseModel):
    """导入批次列表响应。"""
    items: list[BatchListItem]
    total: int


# ============================================================
# 撤销
# ============================================================

class RollbackItem(BaseModel):
    """撤销预览项。"""
    employee_id: int
    employee_name: str
    action: str
    details: str
    reversible: bool
    conflict: bool = False
    conflict_reason: Optional[str] = None


class RollbackPreviewResponse(BaseModel):
    """撤销预览响应。"""
    batch_id: int
    batch_no: str
    can_rollback: bool
    items: list[RollbackItem] = []
    irreversible_operations: list[str] = []
    conflicts: list[str] = []


# ============================================================
# 列别名
# ============================================================

class ColumnAliasItem(BaseModel):
    """列别名。"""
    id: int
    source_header_normalized: str
    target_field_key: str
    enabled: bool


class ValueAliasItem(BaseModel):
    """值别名。"""
    id: int
    field_key: str
    source_value_normalized: str
    target_value: str


class CreateColumnAliasRequest(BaseModel):
    """创建列别名请求。"""
    source_header_normalized: str
    target_field_key: str


class CreateValueAliasRequest(BaseModel):
    """创建值别名请求。"""
    field_key: str
    source_value_normalized: str
    target_value: str

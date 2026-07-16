"""通用 Pydantic schema: 分页参数、统一响应包装。"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """分页查询参数，可直接作为 FastAPI 依赖注入。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: Optional[str] = Field(default=None, description="排序方向: asc 或 desc")


class ApiResponse(BaseModel, Generic[T]):
    """统一成功响应包装。"""

    success: bool = True
    data: T
    request_id: Optional[str] = None


class ApiError(BaseModel):
    """错误信息结构。"""

    code: str
    message: str
    details: Optional[dict] = None

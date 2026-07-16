"""Router 公共工具"""

from __future__ import annotations

from typing import Any

from fastapi import Request


def success_response(data: Any, request: Request = None) -> dict:
    """返回统一成功响应。"""
    result = {"success": True, "data": data}
    if request is not None and hasattr(request.state, "request_id"):
        result["request_id"] = request.state.request_id
    return result


def paged_response(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """返回分页成功响应。"""
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }

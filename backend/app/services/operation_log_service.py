from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session as DBSession

from ..models import OperationLog


def _to_dict(model) -> dict[str, Any]:
    return model.dict()


def create_log(
    db: DBSession,
    operator_id: str,
    object_type: str,
    object_id: str,
    operation_type: str,
    before_data: Any = None,
    after_data: Any = None,
    operation_source: Optional[str] = None,
    business_id: Optional[int] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """创建操作日志。"""
    log = OperationLog(
        operator_id=operator_id,
        operated_at=datetime.now(),
        object_type=object_type,
        object_id=str(object_id),
        operation_type=operation_type,
        before_data=str(before_data) if before_data is not None else None,
        after_data=str(after_data) if after_data is not None else None,
        operation_source=operation_source,
        business_id=business_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)


def get_log(db: DBSession, log_id: int) -> Optional[dict[str, Any]]:
    """获取日志详情。"""
    log = db.query(OperationLog).filter(OperationLog.id == log_id).first()
    if not log:
        return None
    return _to_dict(log)


def list_logs(
    db: DBSession,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    business_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """查询操作日志列表。"""
    query = db.query(OperationLog)

    if object_type:
        query = query.filter(OperationLog.object_type == object_type)
    if object_id:
        query = query.filter(OperationLog.object_id == str(object_id))
    if business_id is not None:
        query = query.filter(OperationLog.business_id == business_id)

    total = query.count()

    items = query.order_by(
        desc(OperationLog.operated_at),
    ).offset((page - 1) * page_size).limit(page_size).all()

    return [_to_dict(i) for i in items], total

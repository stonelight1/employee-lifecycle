"""花名册导入批次查询服务。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from ..models.roster_batch import RosterImportBatch


def list_batches(
    db: DBSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """分页查询花名册导入批次。"""
    query = db.query(RosterImportBatch).filter(RosterImportBatch.is_deleted == False)
    total = query.count()
    batches = (
        query.order_by(RosterImportBatch.created_at.desc(), RosterImportBatch.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_batch_to_item(batch) for batch in batches], total


def _batch_to_item(batch: RosterImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "mode": _value(batch.mode),
        "file_name": batch.file_name,
        "file_sha256": batch.file_sha256,
        "batch_status": _value(batch.batch_status),
        "total_rows": batch.total_rows or 0,
        "new_count": batch.new_count or 0,
        "update_count": batch.update_count or 0,
        "skipped_count": batch.skipped_count or 0,
        "confirmation_count": batch.confirmation_count or 0,
        "error_count": batch.error_count or 0,
        "warning_count": batch.warning_count or 0,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "failed_at": batch.failed_at,
        "rolled_back_at": batch.rolled_back_at,
    }


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value

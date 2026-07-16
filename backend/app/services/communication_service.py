"""
沟通记录 —— 业务逻辑层
"""

from __future__ import annotations

import hashlib
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import CommunicationStatus
from ..exceptions import (
    CommunicationTextTooLong,
    Conflict,
    ResourceDeleted,
    ResourceNotFound,
    VersionConflict,
)
from ..models.ai_summary import AiSummaryVersion
from ..models.communication import CommunicationRecord
from ..models.text_version import CommunicationTextVersion


def compute_text_hash(text: str) -> str:
    """计算文本的 SHA256 哈希。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_next_version_no(db: Session, communication_id: int) -> int:
    """获取沟通记录的下一个文本版本号。"""
    last_version = (
        db.query(CommunicationTextVersion)
        .filter(CommunicationTextVersion.communication_id == communication_id)
        .order_by(desc(CommunicationTextVersion.version_no))
        .first()
    )
    return (last_version.version_no + 1) if last_version else 1


def create_communication(
    db: Session,
    data: dict,
    operator: dict,
) -> dict:
    """创建沟通记录，如有文本同时创建首个版本。"""
    text = data.get("communication_text")
    text_hash = None
    text_length = 0

    if text and text.strip():
        if len(text) > settings.communication_text_max_length:
            raise CommunicationTextTooLong(settings.communication_text_max_length)
        text_hash = compute_text_hash(text)
        text_length = len(text)

    comm = CommunicationRecord(
        employment_id=data["employment_id"],
        followup_task_id=data.get("followup_task_id"),
        communication_type=data.get("communication_type"),
        communication_at=data.get("communication_at"),
        hr_user_id=operator["user_id"],
        communication_status=CommunicationStatus.DRAFT,
        manual_summary=data.get("manual_summary"),
        hr_conclusion=data.get("hr_conclusion"),
        source=data.get("source"),
        current_text_hash=text_hash,
    )
    db.add(comm)
    db.flush()

    if text and text.strip():
        version_no = _get_next_version_no(db, comm.id)
        text_version = CommunicationTextVersion(
            communication_id=comm.id,
            version_no=version_no,
            text_content=text,
            text_hash=text_hash,
            text_length=text_length,
            created_by=operator["user_id"],
        )
        db.add(text_version)
        db.flush()

        comm.current_text_version_id = text_version.id
        comm.current_text_version_no = text_version.version_no
        comm.current_text_hash = text_hash

    db.commit()
    db.refresh(comm)
    return comm.dict()


def update_communication(
    db: Session,
    communication_id: int,
    data: dict,
    operator: dict,
) -> dict:
    """更新沟通记录。

    文本变化时自动创建新版本，同时将旧 AI 总结标记为 stale。
    """
    comm = _get_communication_or_error(db, communication_id)

    # 乐观锁检查
    if "version" in data and data.get("version") is not None:
        if getattr(comm, "version", None) != data["version"]:
            raise VersionConflict("沟通记录已被其他用户修改")

    # 更新标量字段
    _update_scalar_fields(comm, data)

    # 处理文本变化
    if "communication_text" in data:
        _handle_text_change(db, comm, data, operator)

    db.commit()
    db.refresh(comm)
    return comm.dict()


def _update_scalar_fields(comm: CommunicationRecord, data: dict) -> None:
    """更新沟通记录的标量字段。"""
    for field in (
        "communication_at", "manual_summary", "hr_conclusion",
        "communication_type", "followup_task_id",
    ):
        if field in data:
            setattr(comm, field, data[field])


def _handle_text_change(
    db: Session,
    comm: CommunicationRecord,
    data: dict,
    operator: dict,
) -> None:
    """处理沟通文本变更：创建新版本并标记旧 AI 为 stale。"""
    text = data.get("communication_text")

    if len(text) > settings.communication_text_max_length:
        raise CommunicationTextTooLong(settings.communication_text_max_length)

    if text and text.strip():
        text_hash = compute_text_hash(text)
        text_length = len(text)
        version_no = _get_next_version_no(db, comm.id)

        text_version = CommunicationTextVersion(
            communication_id=comm.id,
            version_no=version_no,
            text_content=text,
            text_hash=text_hash,
            text_length=text_length,
            change_reason=data.get("change_reason"),
            created_by=operator["user_id"],
        )
        db.add(text_version)
        db.flush()

        comm.current_text_version_id = text_version.id
        comm.current_text_version_no = text_version.version_no
        comm.current_text_hash = text_hash
    else:
        comm.current_text_version_id = None
        comm.current_text_version_no = None
        comm.current_text_hash = None

    # 标记旧 AI 总结为 stale
    db.query(AiSummaryVersion).filter(
        AiSummaryVersion.communication_id == comm.id,
        AiSummaryVersion.is_stale == False,
    ).update({"is_stale": True})


def _get_communication_or_error(
    db: Session,
    communication_id: int,
) -> CommunicationRecord:
    """获取沟通记录，不存在或已删除时抛出异常。"""
    comm = db.query(CommunicationRecord).filter(
        CommunicationRecord.id == communication_id,
    ).first()
    if not comm:
        raise ResourceNotFound("沟通记录不存在")
    if getattr(comm, "is_deleted", False):
        raise ResourceDeleted("沟通记录已删除")
    return comm


def delete_communication(
    db: Session,
    communication_id: int,
    operator: dict,
) -> None:
    """逻辑删除沟通记录。"""
    comm = _get_communication_or_error(db, communication_id)
    comm.is_deleted = True
    db.commit()


def get_communication(
    db: Session,
    communication_id: int,
) -> dict | None:
    """获取沟通记录详情。"""
    comm = db.query(CommunicationRecord).filter(
        CommunicationRecord.id == communication_id,
    ).first()
    if not comm or getattr(comm, "is_deleted", False):
        return None
    return comm.dict()


def list_communications(
    db: Session,
    employment_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """分页查询沟通记录列表。"""
    query = db.query(CommunicationRecord).filter(
        CommunicationRecord.is_deleted == False,
    )
    if employment_id is not None:
        query = query.filter(CommunicationRecord.employment_id == employment_id)

    total = query.count()
    items = (
        query.order_by(desc(CommunicationRecord.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [item.dict() for item in items], total


def get_text_versions(
    db: Session,
    communication_id: int,
) -> list[dict]:
    """获取沟通文本的历史版本列表。"""
    versions = (
        db.query(CommunicationTextVersion)
        .filter(CommunicationTextVersion.communication_id == communication_id)
        .order_by(CommunicationTextVersion.version_no)
        .all()
    )
    return [v.dict() for v in versions]


def get_text_version(
    db: Session,
    communication_id: int,
    version_no: int,
) -> dict | None:
    """获取指定版本号的沟通文本。"""
    version = (
        db.query(CommunicationTextVersion)
        .filter(
            CommunicationTextVersion.communication_id == communication_id,
            CommunicationTextVersion.version_no == version_no,
        )
        .first()
    )
    return version.dict() if version else None

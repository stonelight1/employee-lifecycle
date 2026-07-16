"""
沟通记录 —— API 路由
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..schemas.communication import (
    CommunicationCreate,
    CommunicationListResponse,
    CommunicationResponse,
    CommunicationUpdate,
    TextVersionResponse,
)
from ..services import communication_service
from ..services.operation_log_service import create_log

router = APIRouter(prefix="/communications", tags=["Communications"])


def _success(data, request_id: str = "") -> dict:
    return {"success": True, "data": data, "request_id": request_id}


def _request_id() -> str:
    return uuid.uuid4().hex[:16]


@router.get("")
def list_communications(
    employment_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取沟通记录列表。"""
    items, total = communication_service.list_communications(
        db, employment_id=employment_id, page=page, page_size=page_size,
    )
    return _success(
        CommunicationListResponse(
            items=[CommunicationResponse.model_validate(item) for item in items],
            total=total,
        ).model_dump(),
        _request_id(),
    )


@router.post("", status_code=201)
def create_communication(
    body: CommunicationCreate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建沟通记录。"""
    result = communication_service.create_communication(
        db, body.model_dump(exclude_unset=True), current_user,
    )
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="COMMUNICATION",
        object_id=result.get("id"),
        operation_type="CREATE",
        after_data=result,
        business_id=result.get("employment_id"),
    )
    return _success(
        CommunicationResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.get("/{communication_id}")
def get_communication(
    communication_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取沟通记录详情。"""
    result = communication_service.get_communication(db, communication_id)
    if not result:
        from ..exceptions import ResourceNotFound
        raise ResourceNotFound("沟通记录不存在")
    return _success(
        CommunicationResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.patch("/{communication_id}")
def update_communication(
    communication_id: int,
    body: CommunicationUpdate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新沟通记录。"""
    old = communication_service.get_communication(db, communication_id)
    result = communication_service.update_communication(
        db, communication_id, body.model_dump(exclude_unset=True), current_user,
    )
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="COMMUNICATION",
        object_id=communication_id,
        operation_type="UPDATE",
        before_data=old,
        after_data=result,
    )
    return _success(
        CommunicationResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.delete("/{communication_id}")
def delete_communication(
    communication_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """逻辑删除沟通记录。"""
    old = communication_service.get_communication(db, communication_id)
    communication_service.delete_communication(db, communication_id, current_user)
    create_log(
        db,
        operator_id=current_user.get("user_id", "system"),
        object_type="COMMUNICATION",
        object_id=communication_id,
        operation_type="DELETE",
        before_data=old,
    )
    return _success(None, _request_id())


@router.get("/{communication_id}/text-versions")
def list_text_versions(
    communication_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取沟通文本的历史版本列表。"""
    versions = communication_service.get_text_versions(db, communication_id)
    return _success(
        [TextVersionResponse.model_validate(v).model_dump() for v in versions],
        _request_id(),
    )


@router.get("/{communication_id}/text-versions/{version_no}")
def get_text_version(
    communication_id: int,
    version_no: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取沟通文本的指定版本。"""
    result = communication_service.get_text_version(db, communication_id, version_no)
    if not result:
        from ..exceptions import ResourceNotFound
        raise ResourceNotFound("文本版本不存在")
    return _success(
        TextVersionResponse.model_validate(result).model_dump(),
        _request_id(),
    )

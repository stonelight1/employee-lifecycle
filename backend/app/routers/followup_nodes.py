"""
跟进节点路由。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..models.followup_node import FollowupNodeDefinition
from ..schemas.followup import (
    FollowupNodeCreate,
    FollowupNodeResponse,
    FollowupNodeUpdate,
    api_success,
)
from ..services import followup_service as svc

router = APIRouter(tags=["跟进节点"])


@router.get("/followup-nodes")
def list_followup_nodes(
    request: Request,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取跟进节点列表（所有未逻辑删除的节点）。"""
    rows = (
        db.query(FollowupNodeDefinition)
        .filter(FollowupNodeDefinition.is_deleted == False)
        .all()
    )
    data = [FollowupNodeResponse.model_validate(r).model_dump() for r in rows]
    return api_success(data=data)


@router.post("/followup-nodes", status_code=201)
def create_followup_node(
    request: Request,
    body: FollowupNodeCreate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建跟进节点。"""
    node = svc.create_node(
        db,
        data=body.model_dump(),
        operator=current_user["user_id"],
    )
    return api_success(
        data=FollowupNodeResponse.model_validate(node).model_dump()
    )


@router.get("/followup-nodes/{node_id}")
def get_followup_node(
    request: Request,
    node_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取跟进节点详情。"""
    node = db.query(FollowupNodeDefinition).filter(
        FollowupNodeDefinition.id == node_id,
    ).first()
    if node is None or node.is_deleted:
        raise ResourceNotFound(f"跟进节点不存在: {node_id}")
    return api_success(
        data=FollowupNodeResponse.model_validate(node).model_dump()
    )


@router.patch("/followup-nodes/{node_id}")
def update_followup_node(
    request: Request,
    node_id: int,
    body: FollowupNodeUpdate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新跟进节点。"""
    node = svc.update_node(
        db,
        node_id=node_id,
        data=body.model_dump(exclude_unset=True),
        operator=current_user["user_id"],
    )
    return api_success(
        data=FollowupNodeResponse.model_validate(node).model_dump()
    )


@router.post("/followup-nodes/{node_id}/enable")
def enable_followup_node(
    request: Request,
    node_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """启用跟进节点。"""
    svc.enable_node(db, node_id=node_id, operator=current_user["user_id"])
    return api_success(data=None)


@router.post("/followup-nodes/{node_id}/disable")
def disable_followup_node(
    request: Request,
    node_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """停用跟进节点。"""
    svc.disable_node(db, node_id=node_id, operator=current_user["user_id"])
    return api_success(data=None)


@router.delete("/followup-nodes/{node_id}")
def delete_followup_node(
    request: Request,
    node_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """逻辑删除跟进节点。"""
    svc.delete_node(db, node_id=node_id, operator=current_user["user_id"])
    return api_success(data=None)

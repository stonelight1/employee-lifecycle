"""
跟进任务路由。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..models.followup_task import FollowupTask
from ..models.followup_participant import FollowupTaskParticipant
from ..schemas.followup import (
    FollowupTaskCreate,
    FollowupTaskListResponse,
    FollowupTaskResponse,
    FollowupTaskUpdate,
    TaskCancelRequest,
    TaskConfirmRequest,
    TaskParticipantAdd,
    api_success,
)
from ..services import followup_service as svc

router = APIRouter(tags=["跟进任务"])


@router.get("/followup-tasks")
def list_followup_tasks(
    request: Request,
    employment_id: int | None = None,
    followup_status: str | None = None,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取跟进任务列表，支持按任职和状态筛选。"""
    q = db.query(FollowupTask).filter(FollowupTask.is_deleted == False)
    if employment_id is not None:
        q = q.filter(FollowupTask.employment_id == employment_id)
    if followup_status is not None:
        q = q.filter(FollowupTask.followup_status == followup_status)
    q = q.order_by(FollowupTask.planned_date.asc())

    rows = q.all()
    data = []
    for r in rows:
        item = FollowupTaskListResponse.model_validate(r).model_dump()
        # 参与人计数
        cnt = (
            db.query(FollowupTaskParticipant)
            .filter(
                FollowupTaskParticipant.task_id == r.id,
                FollowupTaskParticipant.active == True,
            )
            .count()
        )
        item["participant_count"] = cnt
        data.append(item)

    return api_success(data=data)


@router.post("/followup-tasks", status_code=201)
def create_followup_task(
    request: Request,
    body: FollowupTaskCreate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """手工创建跟进任务。"""
    task = svc.create_manual_task(
        db,
        data=body.model_dump(),
        operator=current_user["user_id"],
    )
    detail = svc.get_task_detail(db, task["id"])
    return api_success(
        data=FollowupTaskResponse.model_validate(detail).model_dump()
        if detail
        else None
    )


@router.get("/followup-tasks/{task_id}")
def get_followup_task(
    request: Request,
    task_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取跟进任务详情（含参与人和确认记录）。"""
    task = svc.get_task_detail(db, task_id)
    if task is None:
        raise ResourceNotFound(f"跟进任务不存在: {task_id}")
    return api_success(
        data=FollowupTaskResponse.model_validate(task).model_dump()
    )


@router.patch("/followup-tasks/{task_id}")
def update_followup_task(
    request: Request,
    task_id: int,
    body: FollowupTaskUpdate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """更新跟进任务（受限字段）。"""
    task = svc.update_task(
        db,
        task_id=task_id,
        data=body.model_dump(exclude_unset=True),
        operator=current_user["user_id"],
    )
    detail = svc.get_task_detail(db, task["id"])
    return api_success(
        data=FollowupTaskResponse.model_validate(detail).model_dump()
        if detail
        else None
    )


@router.post("/followup-tasks/{task_id}/start")
def start_followup_task(
    request: Request,
    task_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """开始任务（PENDING -> IN_PROGRESS）。"""
    task = svc.start_task(db, task_id=task_id, operator=current_user["user_id"])
    detail = svc.get_task_detail(db, task["id"])
    return api_success(
        data=FollowupTaskResponse.model_validate(detail).model_dump()
        if detail
        else None
    )


@router.post("/followup-tasks/{task_id}/submit")
def submit_followup_task(
    request: Request,
    task_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """提交任务（IN_PROGRESS -> PENDING_CONFIRMATION）。"""
    task = svc.submit_task(db, task_id=task_id, operator=current_user["user_id"])
    detail = svc.get_task_detail(db, task["id"])
    return api_success(
        data=FollowupTaskResponse.model_validate(detail).model_dump()
        if detail
        else None
    )


@router.post("/followup-tasks/{task_id}/confirm")
def confirm_followup_task(
    request: Request,
    task_id: int,
    body: TaskConfirmRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """确认任务。"""
    svc.confirm_task(
        db,
        task_id=task_id,
        user_id=current_user["user_id"],
        comment=body.comment,
        operator=current_user["user_id"],
    )
    detail = svc.get_task_detail(db, task_id)
    return api_success(
        data=FollowupTaskResponse.model_validate(detail).model_dump()
        if detail
        else None
    )


@router.post("/followup-tasks/{task_id}/reject")
def reject_followup_task(
    request: Request,
    task_id: int,
    body: TaskConfirmRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """驳回任务（PENDING_CONFIRMATION -> IN_PROGRESS）。"""
    svc.reject_task(
        db,
        task_id=task_id,
        user_id=current_user["user_id"],
        comment=body.comment,
        operator=current_user["user_id"],
    )
    detail = svc.get_task_detail(db, task_id)
    return api_success(
        data=FollowupTaskResponse.model_validate(detail).model_dump()
        if detail
        else None
    )


@router.post("/followup-tasks/{task_id}/cancel")
def cancel_followup_task(
    request: Request,
    task_id: int,
    body: TaskCancelRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """取消任务。"""
    svc.cancel_task(
        db,
        task_id=task_id,
        reason=body.reason,
        operator=current_user["user_id"],
    )
    return api_success(data=None)


@router.post("/followup-tasks/{task_id}/participants")
def add_task_participant(
    request: Request,
    task_id: int,
    body: TaskParticipantAdd,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """添加参与人。"""
    svc.add_participant(
        db,
        task_id=task_id,
        user_id=body.user_id,
        role=body.participant_role,
        operator=current_user["user_id"],
    )
    return api_success(data=None)


@router.delete("/followup-tasks/{task_id}/participants/{user_id}")
def remove_task_participant(
    request: Request,
    task_id: int,
    user_id: str,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """移除参与人。"""
    svc.remove_participant(
        db,
        task_id=task_id,
        user_id=user_id,
        operator=current_user["user_id"],
    )
    return api_success(data=None)

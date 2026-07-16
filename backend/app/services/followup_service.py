"""
跟进节点和任务 Service 层 —— 业务逻辑。

使用 dict 参数传递，与路由层解耦。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    ConfirmationMode,
    ConfirmationStatus,
    FollowupTaskStatus,
    ParticipantRole,
    TaskSource,
    TriggerType,
)
from ..exceptions import (
    InvalidStateTransition,
    ResourceDeleted,
    ResourceNotFound,
)
from ..models.followup_node import FollowupNodeDefinition
from ..models.followup_participant import (
    FollowupTaskConfirmation,
    FollowupTaskParticipant,
)
from ..models.followup_task import FollowupTask

# ============================================================
# 默认节点配置
# ============================================================

_DEFAULT_NODES: list[dict[str, Any]] = [
    {
        "node_code": "D7",
        "node_name": "入职后 7 天",
        "trigger_type": TriggerType.DAYS_AFTER_HIRE,
        "offset_days": 7,
        "confirmation_mode": ConfirmationMode.ALL,
    },
    {
        "node_code": "D15",
        "node_name": "入职后 15 天",
        "trigger_type": TriggerType.DAYS_AFTER_HIRE,
        "offset_days": 15,
        "confirmation_mode": ConfirmationMode.ALL,
    },
    {
        "node_code": "D30",
        "node_name": "入职后 30 天",
        "trigger_type": TriggerType.DAYS_AFTER_HIRE,
        "offset_days": 30,
        "confirmation_mode": ConfirmationMode.ALL,
    },
    {
        "node_code": "D45",
        "node_name": "入职后 45 天",
        "trigger_type": TriggerType.DAYS_AFTER_HIRE,
        "offset_days": 45,
        "confirmation_mode": ConfirmationMode.ALL,
    },
    {
        "node_code": "REGULARIZATION_INTERVIEW",
        "node_name": "转正面谈",
        "trigger_type": TriggerType.REGULARIZATION_INTERVIEW,
        "offset_days": None,
        "confirmation_mode": ConfirmationMode.ALL,
    },
]


# ============================================================
# 节点管理
# ============================================================


def create_default_nodes(db: DBSession) -> None:
    """幂等创建默认 7/15/30/45 天和转正面谈节点。"""
    existing = {n.node_code for n in db.query(FollowupNodeDefinition).all()}
    for cfg in _DEFAULT_NODES:
        if cfg["node_code"] not in existing:
            node = FollowupNodeDefinition(
                node_code=cfg["node_code"],
                node_name=cfg["node_name"],
                trigger_type=cfg["trigger_type"],
                offset_days=cfg["offset_days"],
                confirmation_mode=cfg["confirmation_mode"],
                enabled=True,
                node_version=1,
            )
            db.add(node)
    db.flush()


def get_enabled_nodes(db: DBSession) -> list[dict]:
    """获取所有已启用且未逻辑删除的节点。"""
    rows = (
        db.query(FollowupNodeDefinition)
        .filter(
            FollowupNodeDefinition.enabled == True,
            FollowupNodeDefinition.is_deleted == False,
        )
        .all()
    )
    return [_node_to_dict(r) for r in rows]


def _get_node_or_error(db: DBSession, node_id: int) -> FollowupNodeDefinition:
    """按 ID 获取节点，不存在或已逻辑删除时抛异常。"""
    node = db.query(FollowupNodeDefinition).filter(
        FollowupNodeDefinition.id == node_id
    ).first()
    if node is None:
        raise ResourceNotFound(f"跟进节点不存在: {node_id}")
    if node.is_deleted:
        raise ResourceDeleted(f"跟进节点已删除: {node_id}")
    return node


def create_node(db: DBSession, data: dict, operator: str) -> dict:
    """创建跟进节点。"""
    node = FollowupNodeDefinition(
        node_code=data["node_code"],
        node_name=data["node_name"],
        trigger_type=data.get("trigger_type", TriggerType.DAYS_AFTER_HIRE),
        offset_days=data.get("offset_days"),
        confirmation_mode=data.get("confirmation_mode", ConfirmationMode.ALL),
        default_assignee_rule=data.get("default_assignee_rule"),
        effective_from=data.get("effective_from"),
        effective_to=data.get("effective_to"),
        enabled=True,
        node_version=1,
        created_by=operator,
    )
    db.add(node)
    db.flush()
    return _node_to_dict(node)


def update_node(db: DBSession, node_id: int, data: dict, operator: str) -> dict:
    """更新跟进节点。"""
    node = _get_node_or_error(db, node_id)

    updatable = [
        "node_name",
        "offset_days",
        "confirmation_mode",
        "default_assignee_rule",
        "effective_from",
        "effective_to",
    ]
    changed = False
    for key in updatable:
        if key in data:
            setattr(node, key, data[key])
            changed = True

    if changed:
        node.node_version = (node.node_version or 0) + 1
        node.updated_by = operator
        db.flush()

    return _node_to_dict(node)


def delete_node(db: DBSession, node_id: int, operator: str) -> None:
    """逻辑删除跟进节点。"""
    node = _get_node_or_error(db, node_id)
    node.is_deleted = True
    node.updated_by = operator
    db.flush()


def enable_node(db: DBSession, node_id: int, operator: str) -> None:
    """启用节点。"""
    node = _get_node_or_error(db, node_id)
    if not node.enabled:
        node.enabled = True
        node.updated_by = operator
        db.flush()


def disable_node(db: DBSession, node_id: int, operator: str) -> None:
    """停用节点。"""
    node = _get_node_or_error(db, node_id)
    if node.enabled:
        node.enabled = False
        node.updated_by = operator
        db.flush()


# ============================================================
# 任务生成
# ============================================================


def generate_auto_tasks(
    db: DBSession, employment_id: int, hire_date: date
) -> list[dict]:
    """为新任职生成自动任务（幂等）。"""
    nodes = get_enabled_nodes(db)
    results: list[dict] = []

    for node in nodes:
        # 跳过手动触发类型的节点（自动生成不应包含 MANUAL）
        if node.get("trigger_type") == TriggerType.MANUAL:
            continue

        idempotency_key = f"auto_task_{employment_id}_{node['node_code']}"
        existing = (
            db.query(FollowupTask)
            .filter(FollowupTask.idempotency_key == idempotency_key)
            .first()
        )
        if existing is not None:
            results.append(_task_to_dict(existing))
            continue

        # 计算计划日期
        planned_date: date
        offset = node.get("offset_days")
        if offset is not None:
            from datetime import timedelta
            planned_date = hire_date + timedelta(days=offset)
        else:
            # REGULARIZATION_INTERVIEW 类型默认 hire_date + 90 天
            from datetime import timedelta
            planned_date = hire_date + timedelta(days=90)

        task = FollowupTask(
            employment_id=employment_id,
            node_definition_id=node["id"],
            node_version=node.get("node_version", 1),
            node_code_snapshot=node.get("node_code"),
            task_name=node.get("node_name", ""),
            task_source=TaskSource.AUTO,
            trigger_type_snapshot=node.get("trigger_type"),
            offset_days_snapshot=node.get("offset_days"),
            planned_date=planned_date,
            original_planned_date=planned_date,
            date_adjusted_manually=False,
            followup_status=FollowupTaskStatus.PENDING,
            confirmation_mode=node.get("confirmation_mode", ConfirmationMode.ALL),
            idempotency_key=idempotency_key,
        )
        db.add(task)
        db.flush()
        results.append(_task_to_dict(task))

    return results


# ============================================================
# 任务查询
# ============================================================


def get_tasks_by_employment(db: DBSession, employment_id: int) -> list[dict]:
    """获取某任职的所有未逻辑删除任务。"""
    rows = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.employment_id == employment_id,
            FollowupTask.is_deleted == False,
        )
        .order_by(FollowupTask.planned_date.asc())
        .all()
    )
    return [_task_to_dict(r) for r in rows]


def get_task_detail(db: DBSession, task_id: int) -> dict | None:
    """获取任务详情（含参与人和确认记录），不存在时返回 None。"""
    task = db.query(FollowupTask).filter(FollowupTask.id == task_id).first()
    if task is None or task.is_deleted:
        return None

    result = _task_to_dict(task)
    result["participants"] = _get_participants(db, task_id)
    result["confirmations"] = _get_confirmations(db, task_id)
    return result


def _get_task_or_error(db: DBSession, task_id: int) -> FollowupTask:
    """按 ID 获取任务，不存在或已逻辑删除时抛异常。"""
    task = db.query(FollowupTask).filter(FollowupTask.id == task_id).first()
    if task is None:
        raise ResourceNotFound(f"跟进任务不存在: {task_id}")
    if task.is_deleted:
        raise ResourceDeleted(f"跟进任务已删除: {task_id}")
    return task


# ============================================================
# 任务更新 / 手工创建
# ============================================================


def update_task(db: DBSession, task_id: int, data: dict, operator: str) -> dict:
    """更新任务字段（只允许更新特定字段）。"""
    task = _get_task_or_error(db, task_id)

    if "planned_date" in data and data["planned_date"] is not None:
        task.planned_date = data["planned_date"]
    if "date_adjusted_manually" in data:
        task.date_adjusted_manually = data["date_adjusted_manually"]
    if "followup_status" in data and data["followup_status"] is not None:
        # 状态流转校验
        _validate_status_transition(task, data["followup_status"])
        task.followup_status = data["followup_status"]

    task.updated_by = operator
    db.flush()
    return _task_to_dict(task)


def create_manual_task(db: DBSession, data: dict, operator: str) -> dict:
    """手工创建跟进任务。"""
    # 幂等处理
    request_id = data.get("request_id")
    if request_id:
        existing = (
            db.query(FollowupTask)
            .filter(FollowupTask.idempotency_key == request_id)
            .first()
        )
        if existing is not None:
            return _task_to_dict(existing)

    task = FollowupTask(
        employment_id=data["employment_id"],
        task_name=data["task_name"],
        task_source=TaskSource.MANUAL,
        planned_date=data["planned_date"],
        original_planned_date=data["planned_date"],
        date_adjusted_manually=False,
        followup_status=FollowupTaskStatus.PENDING,
        confirmation_mode=data.get("confirmation_mode", ConfirmationMode.ALL),
        idempotency_key=request_id,
        created_by=operator,
    )
    db.add(task)
    db.flush()
    return _task_to_dict(task)


# ============================================================
# 任务状态流转
# ============================================================

_ALLOWED_TRANSITIONS: dict[FollowupTaskStatus, set[FollowupTaskStatus]] = {
    FollowupTaskStatus.PENDING: {
        FollowupTaskStatus.IN_PROGRESS,
        FollowupTaskStatus.CANCELLED,
    },
    FollowupTaskStatus.IN_PROGRESS: {
        FollowupTaskStatus.PENDING_CONFIRMATION,
        FollowupTaskStatus.CANCELLED,
    },
    FollowupTaskStatus.PENDING_CONFIRMATION: {
        FollowupTaskStatus.COMPLETED,
        FollowupTaskStatus.CANCELLED,
    },
    FollowupTaskStatus.COMPLETED: set(),
    FollowupTaskStatus.CANCELLED: set(),
}


def _validate_status_transition(
    task: FollowupTask, target_status: FollowupTaskStatus
) -> None:
    """校验任务状态流转是否合法。"""
    current = FollowupTaskStatus(task.followup_status)
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target_status not in allowed:
        raise InvalidStateTransition(
            f"任务状态不允许从 {current.value} 流转到 {target_status.value}"
        )


def start_task(db: DBSession, task_id: int, operator: str) -> dict:
    """开始任务（PENDING -> IN_PROGRESS）。"""
    task = _get_task_or_error(db, task_id)
    _validate_status_transition(task, FollowupTaskStatus.IN_PROGRESS)
    task.followup_status = FollowupTaskStatus.IN_PROGRESS
    task.updated_by = operator
    db.flush()
    return _task_to_dict(task)


def submit_task(db: DBSession, task_id: int, operator: str) -> dict:
    """提交任务（IN_PROGRESS -> PENDING_CONFIRMATION）。"""
    task = _get_task_or_error(db, task_id)
    _validate_status_transition(task, FollowupTaskStatus.PENDING_CONFIRMATION)
    task.followup_status = FollowupTaskStatus.PENDING_CONFIRMATION
    task.updated_by = operator
    db.flush()
    return _task_to_dict(task)


def cancel_task(
    db: DBSession, task_id: int, reason: str, operator: str
) -> None:
    """取消任务（任意非终态 -> CANCELLED）。"""
    task = _get_task_or_error(db, task_id)
    _validate_status_transition(task, FollowupTaskStatus.CANCELLED)
    task.followup_status = FollowupTaskStatus.CANCELLED
    task.cancel_reason = reason
    task.updated_by = operator
    db.flush()


# ============================================================
# 参与人管理
# ============================================================


def add_participant(
    db: DBSession, task_id: int, user_id: str, role: str, operator: str
) -> dict:
    """添加参与人（幂等）。"""
    task = _get_task_or_error(db, task_id)

    # 检查是否已有有效记录
    existing = (
        db.query(FollowupTaskParticipant)
        .filter(
            FollowupTaskParticipant.task_id == task_id,
            FollowupTaskParticipant.user_id == user_id,
            FollowupTaskParticipant.active == True,
        )
        .first()
    )
    if existing is not None:
        return _participant_to_dict(existing)

    # 如果有非活跃记录，重新激活
    inactive = (
        db.query(FollowupTaskParticipant)
        .filter(
            FollowupTaskParticipant.task_id == task_id,
            FollowupTaskParticipant.user_id == user_id,
            FollowupTaskParticipant.active == False,
        )
        .first()
    )
    if inactive is not None:
        inactive.active = True
        inactive.removed_at = None
        inactive.participant_role = ParticipantRole(role)
        db.flush()
        return _participant_to_dict(inactive)

    participant = FollowupTaskParticipant(
        task_id=task_id,
        user_id=user_id,
        participant_role=ParticipantRole(role),
        active=True,
        created_by=operator,
    )
    db.add(participant)
    db.flush()
    return _participant_to_dict(participant)


def remove_participant(
    db: DBSession, task_id: int, user_id: str, operator: str
) -> None:
    """移除参与人（逻辑移除）。"""
    existing = (
        db.query(FollowupTaskParticipant)
        .filter(
            FollowupTaskParticipant.task_id == task_id,
            FollowupTaskParticipant.user_id == user_id,
            FollowupTaskParticipant.active == True,
        )
        .first()
    )
    if existing is None:
        raise ResourceNotFound(f"参与人不存在或已移除: task={task_id}, user={user_id}")

    existing.active = False
    existing.removed_at = datetime.now()
    db.flush()


# ============================================================
# 确认
# ============================================================


def confirm_task(
    db: DBSession, task_id: int, user_id: str, comment: str | None, operator: str
) -> dict:
    """确认任务（幂等：同一用户重复确认直接返回已有记录）。"""
    task = _get_task_or_error(db, task_id)

    if task.followup_status not in (
        FollowupTaskStatus.PENDING_CONFIRMATION,
        FollowupTaskStatus.IN_PROGRESS,
    ):
        raise InvalidStateTransition(
            f"当前状态 {task.followup_status.value} 不允许确认"
        )

    # 检查重复确认
    existing_conf = (
        db.query(FollowupTaskConfirmation)
        .filter(
            FollowupTaskConfirmation.task_id == task_id,
            FollowupTaskConfirmation.user_id == user_id,
            FollowupTaskConfirmation.confirmation_status
            == ConfirmationStatus.CONFIRMED,
        )
        .first()
    )
    if existing_conf is not None:
        return _confirmation_to_dict(existing_conf)

    confirmation = FollowupTaskConfirmation(
        task_id=task_id,
        user_id=user_id,
        confirmation_status=ConfirmationStatus.CONFIRMED,
        comment=comment,
        confirmed_at=datetime.now(),
    )
    db.add(confirmation)
    db.flush()

    # 检查是否满足完成条件
    check_task_completion(db, task_id)

    return _confirmation_to_dict(confirmation)


def check_task_completion(db: DBSession, task_id: int) -> None:
    """根据确认模式判断任务是否完成。"""
    task = db.query(FollowupTask).filter(FollowupTask.id == task_id).first()
    if task is None:
        return

    if task.followup_status in (FollowupTaskStatus.COMPLETED, FollowupTaskStatus.CANCELLED):
        return

    # 获取所有有效 CONFIRMER 用户
    confirmers = (
        db.query(FollowupTaskParticipant.user_id)
        .filter(
            FollowupTaskParticipant.task_id == task_id,
            FollowupTaskParticipant.active == True,
            FollowupTaskParticipant.participant_role == ParticipantRole.CONFIRMER,
        )
        .all()
    )
    confirmer_ids = {c[0] for c in confirmers}

    if not confirmer_ids:
        # 没有确认人时，标记为 COMPLETED
        _mark_completed(db, task)
        return

    # 获取所有已确认的用户
    confirmed = (
        db.query(FollowupTaskConfirmation.user_id)
        .filter(
            FollowupTaskConfirmation.task_id == task_id,
            FollowupTaskConfirmation.confirmation_status
            == ConfirmationStatus.CONFIRMED,
        )
        .all()
    )
    confirmed_ids = {c[0] for c in confirmed}

    mode = ConfirmationMode(task.confirmation_mode)
    if mode == ConfirmationMode.ALL:
        # 全部确认人已确认
        if confirmer_ids.issubset(confirmed_ids):
            _mark_completed(db, task)
    elif mode == ConfirmationMode.ANY:
        # 任一确认人已确认
        if confirmed_ids & confirmer_ids:
            _mark_completed(db, task)


def _mark_completed(db: DBSession, task: FollowupTask) -> None:
    """将任务标记为已完成。"""
    if task.followup_status == FollowupTaskStatus.COMPLETED:
        return
    task.followup_status = FollowupTaskStatus.COMPLETED
    task.completed_at = datetime.now()
    db.flush()


def reject_task(
    db: DBSession, task_id: int, user_id: str, comment: str | None, operator: str
) -> dict:
    """驳回任务（从 PENDING_CONFIRMATION 回到 IN_PROGRESS）。"""
    task = _get_task_or_error(db, task_id)

    if task.followup_status != FollowupTaskStatus.PENDING_CONFIRMATION:
        raise InvalidStateTransition(
            f"当前状态 {task.followup_status.value} 不允许驳回"
        )

    # 记录驳回确认记录
    confirmation = FollowupTaskConfirmation(
        task_id=task_id,
        user_id=user_id,
        confirmation_status=ConfirmationStatus.PENDING,
        comment=comment,
        confirmed_at=datetime.now(),
    )
    db.add(confirmation)
    db.flush()

    # 将状态退回 IN_PROGRESS
    task.followup_status = FollowupTaskStatus.IN_PROGRESS
    task.updated_by = operator
    db.flush()

    return _confirmation_to_dict(confirmation)


# ============================================================
# 内部辅助
# ============================================================


def _node_to_dict(node: FollowupNodeDefinition) -> dict:
    return {
        "id": node.id,
        "node_code": node.node_code,
        "node_name": node.node_name,
        "trigger_type": node.trigger_type,
        "offset_days": node.offset_days,
        "enabled": node.enabled,
        "default_assignee_rule": node.default_assignee_rule,
        "confirmation_mode": node.confirmation_mode,
        "node_version": node.node_version,
        "effective_from": node.effective_from,
        "effective_to": node.effective_to,
        "is_deleted": node.is_deleted,
        "created_at": node.created_at,
        "created_by": node.created_by,
        "updated_at": node.updated_at,
        "updated_by": node.updated_by,
    }


def _task_to_dict(task: FollowupTask) -> dict:
    return {
        "id": task.id,
        "employment_id": task.employment_id,
        "node_definition_id": task.node_definition_id,
        "node_version": task.node_version,
        "node_code_snapshot": task.node_code_snapshot,
        "task_name": task.task_name,
        "task_source": task.task_source,
        "trigger_type_snapshot": task.trigger_type_snapshot,
        "offset_days_snapshot": task.offset_days_snapshot,
        "planned_date": task.planned_date,
        "original_planned_date": task.original_planned_date,
        "date_adjusted_manually": task.date_adjusted_manually,
        "followup_status": task.followup_status,
        "confirmation_mode": task.confirmation_mode,
        "completed_at": task.completed_at,
        "completed_by": task.completed_by,
        "cancel_reason": task.cancel_reason,
        "idempotency_key": task.idempotency_key,
        "is_deleted": task.is_deleted,
        "created_at": task.created_at,
        "created_by": task.created_by,
        "updated_at": task.updated_at,
        "updated_by": task.updated_by,
    }


def _get_participants(db: DBSession, task_id: int) -> list[dict]:
    rows = (
        db.query(FollowupTaskParticipant)
        .filter(FollowupTaskParticipant.task_id == task_id)
        .order_by(FollowupTaskParticipant.assigned_at.asc())
        .all()
    )
    return [_participant_to_dict(r) for r in rows]


def _participant_to_dict(p: FollowupTaskParticipant) -> dict:
    return {
        "id": p.id,
        "task_id": p.task_id,
        "user_id": p.user_id,
        "participant_role": p.participant_role,
        "active": p.active,
        "assigned_at": p.assigned_at,
        "removed_at": p.removed_at,
        "created_by": p.created_by,
    }


def _get_confirmations(db: DBSession, task_id: int) -> list[dict]:
    rows = (
        db.query(FollowupTaskConfirmation)
        .filter(FollowupTaskConfirmation.task_id == task_id)
        .order_by(FollowupTaskConfirmation.created_at.asc())
        .all()
    )
    return [_confirmation_to_dict(r) for r in rows]


def _confirmation_to_dict(c: FollowupTaskConfirmation) -> dict:
    return {
        "id": c.id,
        "task_id": c.task_id,
        "user_id": c.user_id,
        "confirmation_status": c.confirmation_status,
        "comment": c.comment,
        "confirmed_at": c.confirmed_at,
        "request_id": c.request_id,
        "created_at": c.created_at,
    }

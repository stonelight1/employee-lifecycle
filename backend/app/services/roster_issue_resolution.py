"""花名册导入问题处理服务。

统一问题动作枚举 -> 处理器注册表。
每个动作必须注册对应处理器，未知动作被拒绝。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    IssueAction,
    IssueSeverity,
    ResolutionStatus,
    RosterBatchStatus,
    RosterRowStatus,
)
from ..exceptions import ValidationError
from ..models.roster_batch import RosterImportBatch
from ..models.roster_issue import RosterImportIssue
from ..models.roster_row import RosterImportRow
from .date_utils import parse_date_value


# ============================================================
# 处理器注册表
# ============================================================

# (db, issue, row, batch, value, operator) -> None
IssueHandler = Callable[
    [DBSession, RosterImportIssue, RosterImportRow | None, RosterImportBatch, Any, dict],
    None,
]

_ISSUE_HANDLERS: dict[str, IssueHandler] = {}


def _register(action: IssueAction) -> Callable[[IssueHandler], IssueHandler]:
    """注册问题处理器。"""
    def decorator(handler: IssueHandler) -> IssueHandler:
        _ISSUE_HANDLERS[action.value] = handler
        return handler
    return decorator


def get_handler(action: str) -> IssueHandler | None:
    return _ISSUE_HANDLERS.get(action)


# ============================================================
# 处理器实现
# ============================================================


@_register(IssueAction.MODIFY_VALUE)
def _handle_modify_value(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """修改字段值。

    value 格式: {"field_key": "xxx", "new_value": "xxx"}
    """
    if not row:
        raise ValidationError("问题无关联行，无法修改值")
    if not isinstance(value, dict) or "field_key" not in value:
        raise ValidationError("MODIFY_VALUE 需要 {field_key, new_value} 格式的 value")

    field_key = value["field_key"]
    new_value = value.get("new_value")

    data = _parse_json(row.normalized_data_json)
    data[field_key] = new_value
    row.normalized_data_json = json.dumps(data, ensure_ascii=False, default=str)
    _clear_row_state(row)


@_register(IssueAction.MAP_VALUE)
def _handle_map_value(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """映射组织字典值。

    value 格式: {"field_key": "department", "mapped_value": "技术部"}
    """
    if not row:
        raise ValidationError("问题无关联行，无法映射")
    if not isinstance(value, dict) or "field_key" not in value:
        raise ValidationError("MAP_VALUE 需要 {field_key, mapped_value} 格式的 value")

    field_key = value["field_key"]
    mapped_value = value.get("mapped_value")

    data = _parse_json(row.normalized_data_json)
    data[field_key] = mapped_value
    row.normalized_data_json = json.dumps(data, ensure_ascii=False, default=str)
    _clear_row_state(row)


@_register(IssueAction.SELECT_EMPLOYEE)
def _handle_select_employee(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """选择已存在的员工作为匹配结果。

    value 格式: {"employee_id": 123}
    """
    if not row:
        raise ValidationError("问题无关联行，无法选择员工")
    if not isinstance(value, dict) or "employee_id" not in value:
        raise ValidationError("SELECT_EMPLOYEE 需要 {employee_id} 格式的 value")

    employee_id = int(value["employee_id"])
    row.employee_id = employee_id
    _clear_row_state(row)


@_register(IssueAction.CREATE_NEW_EMPLOYEE)
def _handle_create_new_employee(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """标记为创建新员工（跳过员工匹配，以 NEW 状态处理）。

    value 可选: {"confirmed_name": "张三"}
    """
    if not row:
        raise ValidationError("问题无关联行")
    row.employee_id = None
    row.match_type = None
    row.row_status = RosterRowStatus.NEW
    _clear_row_state(row)


@_register(IssueAction.CONFIRM_REEMPLOYMENT)
def _handle_confirm_reemployment(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """确认重新入职。

    value 可选: {"hire_date": "2026-07-16"}
    """
    if not row:
        raise ValidationError("问题无关联行")
    data = _parse_json(row.normalized_data_json)
    if isinstance(value, dict) and "hire_date" in value:
        parsed = parse_date_value(value["hire_date"])
        if parsed:
            data["hire_date"] = parsed.isoformat()
    data["_reemployment_confirmed"] = True
    row.normalized_data_json = json.dumps(data, ensure_ascii=False, default=str)
    _clear_row_state(row)


@_register(IssueAction.SKIP_ROW)
def _handle_skip_row(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """跳过整行。"""
    if not row:
        # 即使行不存在（如批次级问题），也标记 Issue
        return
    row.row_status = RosterRowStatus.SKIPPED
    row.planned_actions_json = json.dumps({
        "action": "SKIP",
        "reason_code": "MANUAL_SKIP",
        "reason": "用户手动跳过",
    }, ensure_ascii=False)


# ============================================================
# 公共接口
# ============================================================


def resolve_issue(
    db: DBSession,
    issue: RosterImportIssue,
    action: str,
    value: Any,
    note: str | None,
    operator: dict,
) -> RosterImportIssue:
    """处理问题。

    流程：
    1. 查找处理器。
    2. 加载关联行。
    3. 执行处理器（修改 normalized_data / employee_id 等）。
    4. 更新问题状态。

    Raises:
        ValidationError: 未知动作或 BLOCKER 被忽略。
        ValueError: 其他业务错误。
    """
    # 检查动作合法性
    handler = get_handler(action)
    if handler is None:
        raise ValidationError(
            f"未知的问题处理动作「{action}」。"
            f"允许的动作：{', '.join(sorted(_ISSUE_HANDLERS.keys()))}"
        )

    # BLOCKER 不能被 IGNORE
    if issue.severity == IssueSeverity.BLOCKER.value and action == IssueAction.IGNORE.value:
        raise ValidationError("BLOCKER 级别的问题不能忽略，请解决后再试")

    # BLOCKER 不能被 ACCEPT（没有实际处理）
    if issue.severity == IssueSeverity.BLOCKER.value and action == IssueAction.ACCEPT.value:
        raise ValidationError('BLOCKER 级别的问题不能仅"接受"，请选择具体处理动作')

    # 加载行
    row: RosterImportRow | None = None
    if issue.row_id:
        row = db.query(RosterImportRow).filter(RosterImportRow.id == issue.row_id).first()

    # 加载批次
    batch: RosterImportBatch | None = None
    if issue.batch_id:
        batch = db.query(RosterImportBatch).filter(RosterImportBatch.id == issue.batch_id).first()

    # 执行处理器
    handler(db, issue, row, batch, value, operator)

    # 更新问题状态
    if action == IssueAction.SKIP_ROW.value:
        issue.resolution_status = ResolutionStatus.RESOLVED
    elif action == IssueAction.IGNORE.value:
        issue.resolution_status = ResolutionStatus.IGNORED
    elif action == IssueAction.DEFER.value:
        issue.resolution_status = ResolutionStatus.DEFERRED
    else:
        issue.resolution_status = ResolutionStatus.RESOLVED

    issue.resolution_action = action
    if value is not None:
        issue.resolution_value_json = json.dumps(value, ensure_ascii=False, default=str)
    issue.resolution_note = note
    issue.resolved_at = datetime.now()

    db.flush()

    # 检查是否所有 BLOCKER 都已处理 → 更新批次状态为 READY
    if issue.batch_id:
        remaining_blockers = (
            db.query(RosterImportIssue)
            .filter(
                RosterImportIssue.batch_id == issue.batch_id,
                RosterImportIssue.severity == IssueSeverity.BLOCKER.value,
                RosterImportIssue.resolution_status == ResolutionStatus.PENDING.value,
            )
            .count()
        )
        if remaining_blockers == 0:
            batch = db.query(RosterImportBatch).filter(
                RosterImportBatch.id == issue.batch_id
            ).first()
            if batch and batch.batch_status == RosterBatchStatus.WAITING_RESOLUTION.value:
                batch.batch_status = RosterBatchStatus.READY

    return issue


# ============================================================
# 问题重新计算
# ============================================================


RECALC_TRIGGER_ACTIONS = {
    IssueAction.MODIFY_VALUE.value,
    IssueAction.MAP_VALUE.value,
    IssueAction.SELECT_EMPLOYEE.value,
    IssueAction.CREATE_NEW_EMPLOYEE.value,
    IssueAction.CONFIRM_REEMPLOYMENT.value,
}


def needs_recalc(action: str) -> bool:
    """判断该动作是否触发行数据重新计算。"""
    return action in RECALC_TRIGGER_ACTIONS


# ============================================================
# 辅助函数
# ============================================================


def _parse_json(val: str | None) -> dict:
    if not val:
        return {}
    try:
        data = json.loads(val)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _clear_row_state(row: RosterImportRow) -> None:
    """清除行状态，使其在下次预览时重新计算。"""
    row.row_status = RosterRowStatus.NEW  # 重置为 NEW，预览时重新分类
    row.diff_json = None
    row.employee_id = None
    row.match_type = None
    row.planned_actions_json = None
    row.result_json = None

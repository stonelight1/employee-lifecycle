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
    RecommendedAction,
    ResolutionStatus,
    RosterBatchStatus,
    RosterRowStatus,
    ReviewStatus,
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


@_register(IssueAction.IGNORE)
def _handle_ignore(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """忽略问题（仅 WARNING 可用）。

    不做任何业务数据修改，只标记问题状态。
    由 resolve_issue 设置 resolution_status = IGNORED。
    """


@_register(IssueAction.ACCEPT)
def _handle_accept(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """接受/确认问题，标记为已处理。

    仅用于 WARNING / INFO 级别问题，表示 HR 已确认知晓，无需修改业务数据。
    不做任何业务数据修改，只标记问题状态。
    """


@_register(IssueAction.USE_SYSTEM_CALCULATION)
def _handle_use_system_calculation(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """使用系统计算结果，不修改员工业务数据。

    用于 WORK_AGE_MISMATCH、AGE_MISMATCH 等场景：
    - 不修改实际入职日期
    - 不把系统计算值写入固定字段
    - 不保存Excel中的错误值
    - 仅标记问题为已处理，记录系统计算结果用于追溯
    """
    # 此处理器不修改任何业务数据或行数据
    # resolution_value_json 保存系统计算结果用于追溯


@_register(IssueAction.IGNORE_SOURCE_VALUE)
def _handle_ignore_source_value(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """忽略Excel当前字段值，不修改业务数据。

    与 ACCEPT 的区别：明确记录忽略的是Excel字段值而非整个问题。
    """
    # 不修改任何业务数据


@_register(IssueAction.USE_NORMALIZED_VALUE)
def _handle_use_normalized_value(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """使用标准化后的值，不修改员工业务数据。

    用于 KNOWN_COLUMN_ALIAS、KNOWN_VALUE_ALIAS 等场景。
    仅标记问题为已处理，表示 HR 已采用标准化值。
    """


@_register(IssueAction.USE_PARSED_VALUE)
def _handle_use_parsed_value(
    db: DBSession,
    issue: RosterImportIssue,
    row: RosterImportRow | None,
    batch: RosterImportBatch,
    value: Any,
    operator: dict,
) -> None:
    """使用明确解析出的值，不修改员工业务数据。

    用于已明确可解析的日期格式、五险一金标准值等。
    仅标记问题为已处理。
    """


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
            if batch and batch.batch_status in (
                RosterBatchStatus.WAITING_RESOLUTION.value,
                RosterBatchStatus.PREVIEW_READY.value,
            ):
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


# ============================================================
# 批量处理
# ============================================================


def batch_resolve_issues(
    db: DBSession,
    batch_id: int,
    issue_ids: list[int],
    action: str,
    note: str | None,
    operator: dict,
    auto_fixable_check: set[str] | None = None,
) -> dict:
    """批量处理问题（同一批次，单一事务）。

    规则：
    - 所有问题必须在同一批次
    - 所有问题必须为 PENDING 状态
    - action=APPLY_RECOMMENDATION 时需检查 auto_fixable
    - action=IGNORE 时不允许 BLOCKER

    Args:
        db: 数据库会话
        batch_id: 批次ID
        issue_ids: 问题ID列表
        action: 要执行的操作
        note: 备注
        operator: 操作人
        auto_fixable_check: 允许自动处理的问题代码集合

    Returns:
        dict: {total, resolved, skipped, conflicts, failed_ids}

    Raises:
        ValidationError: 参数校验失败
        Exception: 任何业务异常导致整批回滚
    """
    if not issue_ids:
        raise ValidationError("问题ID列表不能为空")

    conflicts: list[dict] = []
    failed_ids: list[int] = []

    # 1. 批量加载问题
    issues = (
        db.query(RosterImportIssue)
        .filter(
            RosterImportIssue.id.in_(issue_ids),
            RosterImportIssue.batch_id == batch_id,
        )
        .all()
    )

    if len(issues) != len(issue_ids):
        found_ids = {i.id for i in issues}
        missing = [iid for iid in issue_ids if iid not in found_ids]
        raise ValidationError(
            f"未找到以下问题（可能不属于当前批次）: {missing}"
        )

    # 2. 检查所有问题为 PENDING
    for issue in issues:
        if issue.resolution_status != ResolutionStatus.PENDING.value:
            conflicts.append({
                "issue_id": issue.id,
                "issue_code": issue.issue_code,
                "reason": f"问题状态为 {issue.resolution_status}，不是 PENDING，无法处理",
            })

    if conflicts:
        return {
            "total": len(issue_ids),
            "resolved": 0,
            "skipped": 0,
            "conflicts": conflicts,
            "failed_ids": [],
        }

    # 3. 按操作类型校验
    if action == IssueAction.APPLY_RECOMMENDATION.value:
        resolved_action = RecommendedAction.USE_SYSTEM_CALCULATION.value
        resolved_note = note or "批量采用系统推荐"

        for issue in issues:
            # 不允许 BLOCKER 自动处理
            if issue.severity == IssueSeverity.BLOCKER.value:
                conflicts.append({
                    "issue_id": issue.id,
                    "issue_code": issue.issue_code,
                    "reason": "BLOCKER 级别问题不允许批量自动处理",
                })
                continue

            # 只处理 auto_fixable 的问题
            if auto_fixable_check and issue.issue_code not in auto_fixable_check:
                conflicts.append({
                    "issue_id": issue.id,
                    "issue_code": issue.issue_code,
                    "reason": f"问题类型 {issue.issue_code} 不允许自动处理，需要人工确认",
                })

        if conflicts:
            return {
                "total": len(issue_ids),
                "resolved": 0,
                "skipped": 0,
                "conflicts": conflicts,
                "failed_ids": [],
            }

    elif action == IssueAction.IGNORE.value:
        resolved_action = IssueAction.IGNORE.value
        resolved_note = note or "批量忽略"

        for issue in issues:
            if issue.severity == IssueSeverity.BLOCKER.value:
                conflicts.append({
                    "issue_id": issue.id,
                    "issue_code": issue.issue_code,
                    "reason": "BLOCKER 级别问题不能忽略",
                })

        if conflicts:
            return {
                "total": len(issue_ids),
                "resolved": 0,
                "skipped": 0,
                "conflicts": conflicts,
                "failed_ids": [],
            }

    else:
        raise ValidationError(f"不支持的批量操作: {action}")

    # 4. 逐个处理（单一事务）
    affected_row_ids: set[int] = set()
    for issue in issues:
        # 再次确认状态没有被其他操作改变
        if issue.resolution_status != ResolutionStatus.PENDING.value:
            conflicts.append({
                "issue_id": issue.id,
                "issue_code": issue.issue_code,
                "reason": "数据已变化，请刷新后重试",
            })
            continue

        try:
            if action == IssueAction.APPLY_RECOMMENDATION.value:
                # 使用 USE_SYSTEM_CALCULATION 或 IGNORE_SOURCE_VALUE
                if issue.issue_code in ("WORK_AGE_MISMATCH", "AGE_MISMATCH"):
                    resolve_action = IssueAction.USE_SYSTEM_CALCULATION.value
                else:
                    resolve_action = IssueAction.IGNORE_SOURCE_VALUE.value

                resolve_issue(db, issue, resolve_action, value={
                    "issue_code": issue.issue_code,
                    "old_value": issue.old_value_json,
                    "new_value": issue.new_value_json,
                }, note=resolved_note, operator=operator)

            elif action == IssueAction.IGNORE.value:
                resolve_issue(db, issue, IssueAction.IGNORE.value,
                              value=None, note=resolved_note, operator=operator)

            if issue.row_id:
                affected_row_ids.add(issue.row_id)

        except Exception as e:
            # 任何异常导致整批回滚
            raise RuntimeError(
                f"批量处理失败，整批回滚。失败问题: issue_id={issue.id}, error={e}"
            ) from e

    # 更新受影响行的审核状态
    if affected_row_ids:
        for row_id in affected_row_ids:
            _update_row_review_status(db, row_id, batch_id)

    db.flush()
    db.commit()

    return {
        "total": len(issues),
        "resolved": len(issues) - len(failed_ids),
        "skipped": 0,
        "conflicts": conflicts,
        "failed_ids": failed_ids,
    }


def _update_row_review_status(db: DBSession, row_id: int, batch_id: int) -> None:
    """更新行的审核状态。

    如果该行所有问题都已处理，设置 review_status = RESOLVED。
    否则保持当前状态。
    """
    row = db.query(RosterImportRow).filter(RosterImportRow.id == row_id).first()
    if not row:
        return

    pending_count = (
        db.query(RosterImportIssue)
        .filter(
            RosterImportIssue.row_id == row_id,
            RosterImportIssue.batch_id == batch_id,
            RosterImportIssue.resolution_status == ResolutionStatus.PENDING.value,
        )
        .count()
    )

    if pending_count == 0:
        row.review_status = ReviewStatus.RESOLVED.value

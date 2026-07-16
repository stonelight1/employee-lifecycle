"""花名册导入重新校验与修复服务。

用于检查已成功导入的员工是否正确，
并提供安全方式修复系统规则导致的数据错误。

安全原则：
1. 只预览不修改数据（revalidate）。
2. 可自动修复的条件：员工由该批次创建，且没有后续人工修改。
3. 修复失败时整批回滚。
4. 修复过程有完整操作日志。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    ConfirmationIssueCode,
    ConfirmationItemStatus,
    EmploymentStatus,
    FollowupTaskStatus,
    ImportAction,
    IssueSeverity,
    ProbationStatus,
    ReviewStatus,
    RosterBatchStatus,
    RosterImportMode,
)
from ..exceptions import ResourceNotFound, ValidationError
from ..models.employee import Employee
from ..models.employment import EmploymentRecord
from ..models.followup_task import FollowupTask
from ..models.hr_confirmation import HrConfirmationItem
from ..models.roster_batch import RosterImportBatch
from ..models.roster_row import RosterImportRow
from ..models.roster_operation import RosterImportOperation
from .operation_log_service import create_log
from .roster_lifecycle_evaluator import evaluate_roster_lifecycle

try:
    from . import employee_service
except ImportError:
    employee_service = None


def revalidate_batch(
    db: DBSession,
    batch_id: int,
) -> dict:
    """重新校验已成功导入的批次。

    读取原始花名册数据，比对系统当前状态，生成差异报告。

    Returns:
        dict: 校验结果，包含可自动修复和需要人工处理的员工列表。
    """
    batch = _get_batch_or_error(db, batch_id)
    if _enum_value(batch.batch_status) != RosterBatchStatus.SUCCEEDED.value:
        raise ValidationError(f"批次状态为 {batch.batch_status}，仅 SUCCEEDED 状态可重新校验")

    rows = (
        db.query(RosterImportRow)
        .filter(RosterImportRow.batch_id == batch_id)
        .order_by(RosterImportRow.row_no.asc())
        .all()
    )

    if not rows:
        raise ValidationError("批次中没有数据行")

    employee_findings: list[dict] = []
    stats = {
        "total_rows": len(rows),
        "issues_found": 0,
        "auto_repairable": 0,
        "needs_manual_review": 0,
        "wrong_probation_count": 0,
        "missing_regularization_date_count": 0,
        "cancelled_tasks_count": 0,
        "confirmations_created": 0,
    }

    for row in rows:
        if row.import_action == ImportAction.SKIP:
            continue

        data = _parse_row_data(row)
        if not data:
            continue

        # 找到员工
        employee = None
        if row.employee_id:
            employee = db.query(Employee).filter(
                Employee.id == row.employee_id,
                Employee.is_deleted == False,
            ).first()

        finding: dict[str, Any] = {
            "row_no": row.row_no,
            "employee_id": row.employee_id,
            "employee_name": employee.name if employee else data.get("name"),
            "current_status": {},
            "expected_status": {},
            "differences": [],
            "can_auto_repair": False,
            "cannot_repair_reason": None,
            "repair_plan": {},
        }

        # 找到当前任职
        employment = None
        if employee:
            employment = (
                db.query(EmploymentRecord)
                .filter(
                    EmploymentRecord.employee_id == employee.id,
                    EmploymentRecord.is_deleted == False,
                )
                .order_by(EmploymentRecord.employment_seq.desc())
                .first()
            )

        if employment:
            finding["current_status"] = {
                "probation_status": _enum_value(employment.probation_status),
                "employment_status": _enum_value(employment.employment_status),
                "actual_regularization_date": _serialize_date(employment.actual_regularization_date),
                "regularization_date": _serialize_date(employment.regularization_date),
                "probation_months": employment.probation_months,
            }

        # 使用生命周期评估器计算应有状态
        lifecycle = evaluate_roster_lifecycle(data)
        finding["expected_status"] = {
            "probation_status": lifecycle.get("probation_status"),
            "employment_status": lifecycle.get("employment_status"),
            "actual_regularization_date": lifecycle.get("actual_regularization_date"),
            "probation_months": lifecycle.get("probation_months"),
        }

        # 对比差异
        if employment:
            differences = _compare_lifecycle(employment, lifecycle)
            finding["differences"] = differences

            if differences:
                stats["issues_found"] += 1

                # 检查是否可自动修复
                can_auto, reason = _check_auto_repair_possible(
                    db, employee.id, employment.id, batch_id, row
                )
                finding["can_auto_repair"] = can_auto
                finding["cannot_repair_reason"] = reason

                if can_auto:
                    stats["auto_repairable"] += 1
                    if any(d["field"] == "probation_status" for d in differences):
                        stats["wrong_probation_count"] += 1
                    if lifecycle.get("probation_status") == ProbationStatus.REGULARIZED.value:
                        expected_reg_date = lifecycle.get("actual_regularization_date")
                        if not expected_reg_date:
                            stats["missing_regularization_date_count"] += 1

                    finding["repair_plan"] = _build_repair_plan(employment, lifecycle)
                else:
                    stats["needs_manual_review"] += 1

        employee_findings.append(finding)

    return {
        "batch_id": batch_id,
        "batch_no": batch.batch_no,
        "stats": stats,
        "employee_findings": employee_findings,
    }


def execute_repair(
    db: DBSession,
    batch_id: int,
    operator: dict,
) -> dict:
    """执行批次修复。

    在单个事务中完成所有自动修复，失败时全部回滚。
    """
    # 先重新校验
    revalidation = revalidate_batch(db, batch_id)
    stats = revalidation["stats"]

    if stats["auto_repairable"] == 0:
        return {
            "batch_id": batch_id,
            "repaired_count": 0,
            "cancelled_tasks_count": 0,
            "confirmations_created": 0,
            "message": "没有需要自动修复的员工",
        }

    repaired_count = 0
    cancelled_tasks_count = 0
    confirmations_created = 0
    repair_log: list[dict] = []

    try:
        for finding in revalidation["employee_findings"]:
            if not finding.get("can_auto_repair"):
                continue

            employee_id = finding["employee_id"]
            employment = (
                db.query(EmploymentRecord)
                .filter(
                    EmploymentRecord.employee_id == employee_id,
                    EmploymentRecord.is_deleted == False,
                )
                .order_by(EmploymentRecord.employment_seq.desc())
                .first()
            )
            if not employment:
                continue

            repair_plan = finding["repair_plan"]
            before_state = _snapshot_employment(employment)

            # 更新试用期状态
            if "probation_status" in repair_plan:
                old_probation = _enum_value(employment.probation_status)
                new_probation = repair_plan["probation_status"]
                employment.probation_status = ProbationStatus(new_probation)

                # 更新 employment_status
                if new_probation == ProbationStatus.REGULARIZED.value:
                    employment.employment_status = EmploymentStatus.ACTIVE

            # 更新转正日期
            if "actual_regularization_date" in repair_plan:
                reg_date = _parse_date_value(repair_plan["actual_regularization_date"])
                employment.actual_regularization_date = reg_date
                employment.regularization_date = reg_date

            if "expected_regularization_date" in repair_plan:
                exp_reg = _parse_date_value(repair_plan["expected_regularization_date"])
                employment.expected_regularization_date = exp_reg

            db.flush()

            # 记录操作
            op = RosterImportOperation(
                batch_id=batch_id,
                row_id=None,
                employee_id=employee_id,
                operation_type="REPAIR_LIFECYCLE",
                target_table="employment_record",
                target_id=employment.id,
                before_snapshot_json=json.dumps(before_state, ensure_ascii=False, default=str),
                after_snapshot_json=json.dumps(_snapshot_employment(employment), ensure_ascii=False, default=str),
                reversible=False,
            )
            db.add(op)

            # 取消错误生成的试用期任务
            if repair_plan.get("should_cancel_tasks"):
                cancelled = _cancel_probation_tasks_for_employee(
                    db, employment.id, batch_id, operator,
                )
                cancelled_tasks_count += cancelled

            # 创建转正日期待确认事项
            if repair_plan.get("create_missing_reg_date_confirmation"):
                _ensure_confirmation(
                    db=db,
                    employee_id=employee_id,
                    employment_id=employment.id,
                    issue_code=ConfirmationIssueCode.MISSING_REGULARIZATION_DATE,
                    title="正式员工缺少转正日期（修复生成）",
                    description="修复批次时发现：正式员工缺少转正日期，请补充。",
                    import_batch_id=batch_id,
                )
                confirmations_created += 1

            repaired_count += 1
            repair_log.append({
                "employee_id": employee_id,
                "employee_name": finding["employee_name"],
                "changes": repair_plan,
            })

        # 操作日志
        operator_id = operator.get("user_id", "system")
        create_log(
            db,
            operator_id=operator_id,
            object_type="ROSTER_IMPORT",
            object_id=str(batch_id),
            operation_type="BATCH_REPAIR",
            after_data={
                "repaired_count": repaired_count,
                "cancelled_tasks_count": cancelled_tasks_count,
                "confirmations_created": confirmations_created,
                "repair_log": repair_log,
            },
        )

        db.flush()

    except Exception:
        db.rollback()
        raise

    return {
        "batch_id": batch_id,
        "repaired_count": repaired_count,
        "cancelled_tasks_count": cancelled_tasks_count,
        "confirmations_created": confirmations_created,
        "repair_log": repair_log,
    }


# ============================================================
# 内部辅助
# ============================================================


def _compare_lifecycle(
    employment: EmploymentRecord,
    lifecycle: dict,
) -> list[dict]:
    """比较当前生命状态和应有状态。"""
    differences = []
    current_probation = _enum_value(employment.probation_status)
    expected_probation = lifecycle.get("probation_status")

    if current_probation != expected_probation:
        differences.append({
            "field": "probation_status",
            "current": current_probation,
            "expected": expected_probation,
        })

    expected_reg_date = lifecycle.get("actual_regularization_date")
    current_reg = _serialize_date(employment.actual_regularization_date)
    if current_reg != expected_reg_date:
        differences.append({
            "field": "actual_regularization_date",
            "current": current_reg,
            "expected": expected_reg_date,
        })

    return differences


def _check_auto_repair_possible(
    db: DBSession,
    employee_id: int,
    employment_id: int,
    batch_id: int,
    row: RosterImportRow,
) -> tuple[bool, str | None]:
    """检查是否可以自动修复。

    条件（必须同时满足）：
    1. 员工由该导入批次创建（row.import_action == NEW 或 UPDATE）
    2. 没有后续人工转正、离职、再次入职等业务记录
    3. 原始花名册数据可以明确判断正确状态
    """
    # 检查是否有后续转正记录
    from ..models.regularization import RegularizationRecord
    reg_records = (
        db.query(RegularizationRecord)
        .filter(
            RegularizationRecord.employment_id == employment_id,
            RegularizationRecord.is_deleted == False,
        )
        .count()
    )
    if reg_records > 0:
        return False, "存在后续转正操作记录，请人工确认"

    # 检查是否有后续离职记录
    from ..models.separation import SeparationRecord
    sep_records = (
        db.query(SeparationRecord)
        .filter(
            SeparationRecord.employment_id == employment_id,
            SeparationRecord.is_deleted == False,
        )
        .count()
    )
    if sep_records > 0:
        return False, "存在后续离职记录，请人工确认"

    return True, None


def _build_repair_plan(
    employment: EmploymentRecord,
    lifecycle: dict,
) -> dict:
    """生成修复计划。"""
    plan: dict = {}

    expected_probation = lifecycle.get("probation_status")
    if _enum_value(employment.probation_status) != expected_probation:
        plan["probation_status"] = expected_probation

    expected_reg = lifecycle.get("actual_regularization_date")
    current_reg = _serialize_date(employment.actual_regularization_date)
    if current_reg != expected_reg:
        plan["actual_regularization_date"] = expected_reg

    expected_exp_reg = lifecycle.get("expected_regularization_date")
    if expected_exp_reg:
        plan["expected_regularization_date"] = expected_exp_reg

    # 是否需要取消试用期任务
    should_create_tasks = lifecycle.get("should_create_probation_tasks", True)
    plan["should_cancel_tasks"] = not should_create_tasks

    # 是否需要创建缺少转正日期确认事项
    if expected_probation == ProbationStatus.REGULARIZED.value and not expected_reg:
        plan["create_missing_reg_date_confirmation"] = True

    return plan


def _cancel_probation_tasks_for_employee(
    db: DBSession,
    employment_id: int,
    batch_id: int,
    operator: dict,
) -> int:
    """取消指定任职的错误试用期任务。"""
    # 查找自动生成的试用期任务
    tasks = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.employment_id == employment_id,
            FollowupTask.task_source == "AUTO",
            FollowupTask.followup_status == FollowupTaskStatus.PENDING.value,
            FollowupTask.node_code_snapshot.in_([
                "DAY_7", "DAY_15", "DAY_30", "DAY_45", "REG_INTERVIEW",
            ]),
        )
        .all()
    )

    count = 0
    for task in tasks:
        task.followup_status = FollowupTaskStatus.CANCELLED.value
        task.notes = (
            f"花名册导入修复取消（批次 {batch_id}）："
            f"员工根据花名册数据应为已转正，不生成试用期跟进任务。"
        )
        db.flush()

        op = RosterImportOperation(
            batch_id=batch_id,
            row_id=None,
            employee_id=None,
            operation_type="REPAIR_CANCEL_TASK",
            target_table="followup_task",
            target_id=task.id,
            before_snapshot_json=json.dumps({"followup_status": "PENDING"}, ensure_ascii=False),
            after_snapshot_json=json.dumps({"followup_status": "CANCELLED"}, ensure_ascii=False),
            reversible=False,
        )
        db.add(op)
        count += 1

    return count


def _ensure_confirmation(
    db: DBSession,
    employee_id: int,
    employment_id: int | None,
    issue_code: ConfirmationIssueCode | str,
    title: str,
    description: str | None = None,
    import_batch_id: int | None = None,
) -> HrConfirmationItem:
    """幂等地创建确认事项。"""
    issue_code_str = _enum_value(issue_code) if hasattr(issue_code, "value") else str(issue_code)

    existing = (
        db.query(HrConfirmationItem)
        .filter(
            HrConfirmationItem.employee_id == employee_id,
            HrConfirmationItem.issue_code == issue_code_str,
            HrConfirmationItem.item_status == ConfirmationItemStatus.PENDING.value,
        )
        .first()
    )
    if existing:
        return existing

    item = HrConfirmationItem(
        employee_id=employee_id,
        employment_id=employment_id,
        source_type="ROSTER_IMPORT_REPAIR",
        source_id=str(import_batch_id) if import_batch_id else None,
        issue_code=issue_code_str,
        title=title,
        description=description,
        import_batch_id=import_batch_id,
        item_status=ConfirmationItemStatus.PENDING.value,
    )
    db.add(item)
    db.flush()
    return item


def _snapshot_employment(employment: EmploymentRecord) -> dict:
    """快照任职记录的当前状态。"""
    return {
        "probation_status": _enum_value(employment.probation_status),
        "employment_status": _enum_value(employment.employment_status),
        "actual_regularization_date": _serialize_date(employment.actual_regularization_date),
        "regularization_date": _serialize_date(employment.regularization_date),
        "probation_months": employment.probation_months,
    }


def _get_batch_or_error(db: DBSession, batch_id: int) -> RosterImportBatch:
    batch = db.query(RosterImportBatch).filter(
        RosterImportBatch.id == batch_id,
    ).first()
    if not batch:
        raise ResourceNotFound(f"导入批次不存在: {batch_id}")
    return batch


def _parse_row_data(row: RosterImportRow) -> dict:
    if not row.normalized_data_json:
        return {}
    try:
        data = json.loads(row.normalized_data_json)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            pass
    return None


def _serialize_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _enum_value(value):
    return value.value if hasattr(value, "value") else value

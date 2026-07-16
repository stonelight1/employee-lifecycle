"""任职业务逻辑（参数使用 dict，返回 dict）。"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..enums import (
    EmploymentStatus,
    FollowupTaskStatus,
    ProbationStatus,
    TaskSource,
)
from ..exceptions import (
    ActiveEmploymentExists,
    InvalidStateTransition,
    ResourceDeleted,
    ResourceNotFound,
    ValidationError,
)
from ..models.employee import Employee
from ..models.employment import EmploymentRecord
from ..models.followup_task import FollowupTask
from .followup_service import generate_auto_tasks
from .operation_log_service import create_log


def _get_active_employment(db: Session, employment_id: int) -> EmploymentRecord:
    """查询未删除的任职记录。"""
    rec = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.id == employment_id)
        .first()
    )
    if not rec:
        raise ResourceNotFound("任职记录不存在")
    if rec.is_deleted:
        raise ResourceDeleted("任职记录已删除")
    return rec


def _get_active_employee(db: Session, employee_id: int) -> Employee:
    """查询未删除的员工。"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ResourceNotFound("员工不存在")
    if emp.is_deleted:
        raise ResourceDeleted("员工已删除")
    return emp


def calculate_probation_end_date(hire_date: date, probation_months: int = 3) -> date:
    """
    计算试用期结束日期。

    规则：入职日期 + probation_months 个自然月。
    同日原则 —— 目标月份不存在同日时取该月最后一天。
    """
    target_month = hire_date.month + probation_months
    target_year = hire_date.year + (target_month - 1) // 12
    target_month = (target_month - 1) % 12 + 1
    last_day = calendar.monthrange(target_year, target_month)[1]
    target_day = min(hire_date.day, last_day)
    return date(target_year, target_month, target_day)


def create_employment(db: Session, data: dict, operator: dict) -> dict:
    """创建任职记录。"""
    employee_id = data.get("employee_id")
    if not employee_id:
        raise ValidationError("employee_id 不能为空")

    _get_active_employee(db, employee_id)

    # 检查是否存在有效任职（防止重复创建）
    active = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.employment_status.in_(
                [
                    EmploymentStatus.PENDING,
                    EmploymentStatus.ACTIVE,
                    EmploymentStatus.SEPARATING,
                ]
            ),
            EmploymentRecord.is_deleted == False,
        )
        .first()
    )
    if active:
        raise ActiveEmploymentExists()

    # 确定 employment_seq
    max_seq = (
        db.query(EmploymentRecord.employment_seq)
        .filter(EmploymentRecord.employee_id == employee_id)
        .order_by(EmploymentRecord.employment_seq.desc())
        .first()
    )
    employment_seq = (max_seq[0] if max_seq else 0) + 1

    hire_date = data.get("hire_date")
    if not hire_date:
        raise ValidationError("hire_date 不能为空")

    probation_months = data.get("probation_months", 3)
    if not isinstance(probation_months, int) or probation_months < 1 or probation_months > 6:
        raise ValidationError("probation_months 必须在 1-6 之间")

    today = date.today()
    if hire_date > today:
        emp_status = EmploymentStatus.PENDING
        prob_status = ProbationStatus.NOT_STARTED
        expected_hire_date = hire_date
        actual_hire_date = None
    else:
        emp_status = EmploymentStatus.ACTIVE
        prob_status = ProbationStatus.IN_PROGRESS
        expected_hire_date = hire_date
        actual_hire_date = hire_date

    probation_end = calculate_probation_end_date(hire_date, probation_months)

    rec = EmploymentRecord(
        employee_id=employee_id,
        employment_seq=employment_seq,
        employment_status=emp_status,
        hire_date=hire_date,
        expected_hire_date=expected_hire_date,
        actual_hire_date=actual_hire_date,
        probation_months=probation_months,
        probation_start_date=hire_date,
        probation_end_date=probation_end,
        probation_status=prob_status,
        department=data.get("department"),
        position=data.get("position"),
        manager_name=data.get("manager_name"),
        date_rule_source="AUTO",
        probation_end_date_source="AUTO",
        created_by=operator.get("user_id", "system"),
    )
    db.add(rec)
    db.flush()
    return rec.dict()


def update_employment(
    db: Session, employment_id: int, data: dict, operator: dict
) -> dict:
    """更新任职信息（部门 / 岗位 / 直属负责人）。"""
    rec = _get_active_employment(db, employment_id)

    if "department" in data:
        rec.department = data["department"]
    if "position" in data:
        rec.position = data["position"]
    if "manager_name" in data:
        rec.manager_name = data["manager_name"]

    rec.updated_by = operator.get("user_id", "system")
    rec.version = (rec.version or 0) + 1
    db.flush()
    return rec.dict()


def get_employment(db: Session, employment_id: int) -> Optional[dict]:
    """获取单条任职详情。"""
    rec = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.id == employment_id)
        .first()
    )
    if not rec:
        return None
    return rec.dict()


def list_employee_employments(db: Session, employee_id: int) -> tuple[list[dict], int]:
    """查询员工的未删除任职记录，按任职序号倒序返回。"""
    _get_active_employee(db, employee_id)
    query = db.query(EmploymentRecord).filter(
        EmploymentRecord.employee_id == employee_id,
        EmploymentRecord.is_deleted == False,
    )
    total = query.count()
    records = query.order_by(EmploymentRecord.employment_seq.desc()).all()
    return [rec.dict() for rec in records], total


def preview_date_change(
    db: Session, employment_id: int, new_hire_date: date
) -> dict:
    """预览入职日期修改的影响。"""
    rec = _get_active_employment(db, employment_id)
    old_hire_date = rec.hire_date
    old_prob_end = rec.probation_end_date
    new_prob_end = calculate_probation_end_date(new_hire_date, rec.probation_months)

    # 查询该任职的所有跟进任务
    tasks: list[FollowupTask] = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.employment_id == employment_id,
            FollowupTask.is_deleted == False,
        )
        .all()
    )

    recalculated: list[dict] = []
    not_modified: list[dict] = []

    for task in tasks:
        # 符合重算条件：自动生成 + PENDING + 未人工调期
        if (
            task.task_source == TaskSource.AUTO
            and task.followup_status == FollowupTaskStatus.PENDING
            and not task.date_adjusted_manually
        ):
            offset = task.offset_days_snapshot or 0
            new_planned = new_hire_date + timedelta(days=offset)
            recalculated.append(
                {
                    "task_id": task.id,
                    "task_name": task.task_name,
                    "planned_date": task.planned_date,
                    "new_planned_date": new_planned,
                    "reason": None,
                }
            )
        else:
            reasons = []
            if task.task_source != TaskSource.AUTO:
                reasons.append("人工创建任务")
            if task.followup_status != FollowupTaskStatus.PENDING:
                reasons.append(f"状态为 {task.followup_status.value}，非 PENDING")
            if task.date_adjusted_manually:
                reasons.append("已人工调期")

            not_modified.append(
                {
                    "task_id": task.id,
                    "task_name": task.task_name,
                    "planned_date": task.planned_date,
                    "new_planned_date": None,
                    "reason": "; ".join(reasons),
                }
            )

    return {
        "old_hire_date": old_hire_date,
        "new_hire_date": new_hire_date,
        "old_probation_end_date": old_prob_end,
        "new_probation_end_date": new_prob_end,
        "recalculated_tasks": recalculated,
        "not_modified_tasks": not_modified,
    }


def confirm_date_change(
    db: Session, employment_id: int, new_hire_date: date, operator: dict
) -> dict:
    """确认入职日期修改（同一事务更新任职和符合条件的任务）。"""
    rec = _get_active_employment(db, employment_id)

    # 更新任职日期
    rec.hire_date = new_hire_date
    rec.probation_start_date = new_hire_date
    rec.probation_end_date = calculate_probation_end_date(new_hire_date, rec.probation_months)
    rec.date_rule_source = "MANUAL"
    rec.probation_end_date_source = "AUTO"

    # 重新判断任职状态：日期改到未来时回退为 PENDING
    today = date.today()
    if new_hire_date > today and rec.employment_status not in [
        EmploymentStatus.SEPARATING,
        EmploymentStatus.SEPARATED,
    ]:
        rec.employment_status = EmploymentStatus.PENDING
        rec.probation_status = ProbationStatus.NOT_STARTED

    rec.updated_by = operator.get("user_id", "system")
    rec.version = (rec.version or 0) + 1

    # 更新符合重算条件的跟进任务
    tasks: list[FollowupTask] = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.employment_id == employment_id,
            FollowupTask.is_deleted == False,
            FollowupTask.task_source == TaskSource.AUTO,
            FollowupTask.followup_status == FollowupTaskStatus.PENDING,
            FollowupTask.date_adjusted_manually == False,
        )
        .all()
    )

    for task in tasks:
        offset = task.offset_days_snapshot or 0
        task.planned_date = new_hire_date + timedelta(days=offset)

    db.flush()
    return rec.dict()


def confirm_hire(
    db: Session,
    employment_id: int,
    actual_hire_date: date | None,
    operator: dict,
) -> dict:
    """确认入职：将 PENDING 状态的任职转为 ACTIVE。"""
    rec = _get_active_employment(db, employment_id)

    if rec.employment_status != EmploymentStatus.PENDING:
        raise InvalidStateTransition("只有 PENDING 状态的任职才能确认入职")

    today = date.today()
    if actual_hire_date is None:
        actual_hire_date = today
    if actual_hire_date > today:
        raise ValidationError("actual_hire_date 不能晚于今天")

    operator_id = operator.get("user_id", "system")
    before = rec.dict()

    # 更新状态与日期
    rec.actual_hire_date = actual_hire_date
    rec.employment_status = EmploymentStatus.ACTIVE
    rec.probation_status = ProbationStatus.IN_PROGRESS
    rec.probation_start_date = actual_hire_date
    rec.probation_end_date = calculate_probation_end_date(
        actual_hire_date, rec.probation_months
    )
    rec.updated_by = operator_id
    rec.version = (rec.version or 0) + 1

    db.flush()

    # 生成自动跟进任务
    generate_auto_tasks(db, employment_id, actual_hire_date)

    # 写操作日志
    after = rec.dict()
    create_log(
        db,
        operator_id=operator_id,
        object_type="EMPLOYMENT",
        object_id=str(employment_id),
        operation_type="CONFIRM_HIRE",
        before_data=before,
        after_data=after,
    )

    db.flush()
    return rec.dict()


def cancel_hire(
    db: Session,
    employment_id: int,
    reasons_json: str,
    note: str,
    operator: dict,
) -> dict:
    """取消入职：将 PENDING 状态的任职标记为 CANCELLED。"""
    rec = _get_active_employment(db, employment_id)

    if rec.employment_status != EmploymentStatus.PENDING:
        raise InvalidStateTransition("只有 PENDING 状态的任职才能取消入职")

    operator_id = operator.get("user_id", "system")
    before = rec.dict()

    rec.employment_status = EmploymentStatus.CANCELLED
    rec.hire_cancel_reasons_json = reasons_json
    rec.hire_cancel_note = note or None
    rec.hire_cancelled_at = datetime.now()
    rec.updated_by = operator_id
    rec.version = (rec.version or 0) + 1

    db.flush()

    after = rec.dict()
    create_log(
        db,
        operator_id=operator_id,
        object_type="EMPLOYMENT",
        object_id=str(employment_id),
        operation_type="CANCEL_HIRE",
        before_data=before,
        after_data=after,
    )

    db.flush()
    return rec.dict()


def restore_hire(
    db: Session,
    employment_id: int,
    new_expected_hire_date: date,
    operator: dict,
) -> dict:
    """恢复入职：将 CANCELLED 状态的任职恢复为 PENDING。"""
    rec = _get_active_employment(db, employment_id)

    if rec.employment_status != EmploymentStatus.CANCELLED:
        raise InvalidStateTransition("只有 CANCELLED 状态的任职才能恢复入职")

    operator_id = operator.get("user_id", "system")
    before = rec.dict()

    rec.employment_status = EmploymentStatus.PENDING
    rec.expected_hire_date = new_expected_hire_date
    rec.hire_cancel_reasons_json = None
    rec.hire_cancel_note = None
    rec.hire_cancelled_at = None
    rec.updated_by = operator_id
    rec.version = (rec.version or 0) + 1

    db.flush()

    after = rec.dict()
    create_log(
        db,
        operator_id=operator_id,
        object_type="EMPLOYMENT",
        object_id=str(employment_id),
        operation_type="RESTORE_HIRE",
        before_data=before,
        after_data=after,
    )

    db.flush()
    return rec.dict()

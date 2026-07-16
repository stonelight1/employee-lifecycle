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
    ResourceDeleted,
    ResourceNotFound,
    ValidationError,
)
from ..models.employee import Employee
from ..models.employment import EmploymentRecord
from ..models.followup_task import FollowupTask


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


def calculate_probation_end_date(hire_date: date) -> date:
    """
    计算默认试用期结束日期。

    规则：入职日期 + 3 个自然月。
    同日原则 —— 目标月份不存在同日时取该月最后一天。
    """
    target_month = hire_date.month + 3
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

    today = date.today()
    if hire_date > today:
        emp_status = EmploymentStatus.PENDING
        prob_status = ProbationStatus.NOT_STARTED
    else:
        emp_status = EmploymentStatus.ACTIVE
        prob_status = ProbationStatus.IN_PROGRESS

    probation_end = calculate_probation_end_date(hire_date)

    rec = EmploymentRecord(
        employee_id=employee_id,
        employment_seq=employment_seq,
        employment_status=emp_status,
        hire_date=hire_date,
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


def preview_date_change(
    db: Session, employment_id: int, new_hire_date: date
) -> dict:
    """预览入职日期修改的影响。"""
    rec = _get_active_employment(db, employment_id)
    old_hire_date = rec.hire_date
    old_prob_end = rec.probation_end_date
    new_prob_end = calculate_probation_end_date(new_hire_date)

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
    rec.probation_end_date = calculate_probation_end_date(new_hire_date)
    rec.date_rule_source = "MANUAL"
    rec.probation_end_date_source = "AUTO"

    # 重新判断任职状态
    today = date.today()
    if new_hire_date > today and rec.employment_status not in [
        EmploymentStatus.SEPARATING,
        EmploymentStatus.SEPARATED,
    ]:
        rec.employment_status = EmploymentStatus.PENDING
        rec.probation_status = ProbationStatus.NOT_STARTED
    elif (
        new_hire_date <= today
        and rec.employment_status == EmploymentStatus.PENDING
    ):
        rec.employment_status = EmploymentStatus.ACTIVE
        rec.probation_status = ProbationStatus.IN_PROGRESS

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

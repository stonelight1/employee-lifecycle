"""聚合查询路由：工作台概览、工作事项聚合、异动离职聚合、试用期聚合。"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db_session
from ..enums import (
    EmploymentStatus,
    FollowupTaskStatus,
    ProbationStatus,
    TodoStatus,
    RiskLevel,
)
from ..models.employee import Employee
from ..models.employment import EmploymentRecord
from ..models.followup_task import FollowupTask
from ..models.change import EmploymentChange
from ..models.separation import SeparationRecord
from ..models.todo import SystemTodo
from ..services.employee_service import (
    resolve_lifecycle_stage,
)
from ..services.risk_query import latest_risks_by_employment, risk_level_value

router = APIRouter(tags=["聚合查询"])


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


@router.get("/dashboard/overview")
def get_dashboard_overview(
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """工作台概览：一次返回所有指标和列表数据。"""
    today = date.today()

    # 获取所有有效员工
    employees = (
        db.query(Employee)
        .filter(Employee.is_deleted == False)
        .all()
    )

    # 获取所有有效任职
    all_employments = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.is_deleted == False)
        .all()
    )
    emp_by_id: dict[int, EmploymentRecord] = {}
    employment_by_id: dict[int, EmploymentRecord] = {}
    for e in all_employments:
        employment_by_id[e.id] = e
        # 只取每个员工最新的一条任职记录
        if e.employee_id not in emp_by_id or e.employment_seq > emp_by_id[e.employee_id].employment_seq:
            emp_by_id[e.employee_id] = e

    # 统计生命周期分布
    lifecycle_counts: dict[str, int] = {
        "PENDING": 0,
        "PROBATION": 0,
        "REGULARIZATION_PENDING": 0,
        "ACTIVE": 0,
        "SEPARATING": 0,
        "SEPARATED": 0,
    }
    probation_count = 0
    active_count = 0

    for emp in employees:
        current_emp = emp_by_id.get(emp.id)
        stage = resolve_lifecycle_stage(current_emp) if current_emp else "UNKNOWN"
        if stage in lifecycle_counts:
            lifecycle_counts[stage] += 1
        if stage == "PROBATION":
            probation_count += 1
        if stage in ("ACTIVE", "PROBATION", "REGULARIZATION_PENDING"):
            active_count += 1

    # 获取所有 PENDING/IN_PROGRESS 跟进任务
    pending_tasks = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.is_deleted == False,
            FollowupTask.followup_status.in_(
                [FollowupTaskStatus.PENDING, FollowupTaskStatus.IN_PROGRESS]
            ),
        )
        .all()
    )

    # 获取所有 PENDING 待办
    pending_todos = (
        db.query(SystemTodo)
        .filter(SystemTodo.todo_status == TodoStatus.PENDING)
        .all()
    )

    # 统计逾期
    overdue_tasks = [t for t in pending_tasks if t.planned_date and t.planned_date < today]
    overdue_todos = [t for t in pending_todos if t.due_at and t.due_at < today]

    # 7天内待转正（probation_end_date 在7天内且未转正）
    regularization_due_7d = 0
    for emp_rec in all_employments:
        if (
            emp_rec.probation_status in (ProbationStatus.IN_PROGRESS, ProbationStatus.PENDING_REVIEW)
            and emp_rec.probation_end_date
            and today <= emp_rec.probation_end_date <= today + timedelta(days=7)
        ):
            regularization_due_7d += 1
        elif (
            emp_rec.probation_status == ProbationStatus.IN_PROGRESS
            and emp_rec.probation_end_date
            and emp_rec.probation_end_date < today
        ):
            regularization_due_7d += 1  # 已超期也算

    # 构建重点事项（逾期+今天到期的）
    priority_items = []
    for task in overdue_tasks:
        emp_rec = employment_by_id.get(task.employment_id)
        emp_name = ""
        dept = ""
        pos = ""
        if emp_rec:
            emp_obj = db.query(Employee).filter(Employee.id == emp_rec.employee_id).first()
            if emp_obj:
                emp_name = emp_obj.name
                dept = emp_rec.department or ""
                pos = emp_rec.position or ""
        priority_items.append({
            "id": f"FOLLOWUP_TASK_{task.id}",
            "source_type": "FOLLOWUP_TASK",
            "source_id": task.id,
            "employee_name": emp_name,
            "department": dept,
            "position": pos,
            "title": task.task_name,
            "due_at": str(task.planned_date),
            "overdue_days": (today - task.planned_date).days,
            "risk_level": "NONE",
        })
    for todo in overdue_todos:
        priority_items.append({
            "id": f"TODO_{todo.id}",
            "source_type": "TODO",
            "source_id": todo.id,
            "employee_name": "",
            "department": "",
            "position": "",
            "title": todo.title,
            "due_at": str(todo.due_at),
            "overdue_days": (today - todo.due_at).days if todo.due_at else 0,
            "risk_level": "NONE",
        })

    # 生命周期分布
    distribution = [
        {"stage": k, "count": v}
        for k, v in lifecycle_counts.items()
        if v > 0
    ]

    # 预警员工（批量查询最新风险，消除逐员工查询）
    recent_risk_employees = []
    risk_candidates = []
    for emp in employees:
        current_emp = emp_by_id.get(emp.id)
        if current_emp:
            risk_candidates.append((emp, current_emp))

    if risk_candidates:
        candidate_employment_ids = [current_emp.id for _, current_emp in risk_candidates]
        emp_id_to_risk = latest_risks_by_employment(db, candidate_employment_ids)

        for emp, current_emp in risk_candidates:
            latest_risk = emp_id_to_risk.get(current_emp.id)
            if latest_risk:
                risk_level = risk_level_value(latest_risk)
                if risk_level in ("MEDIUM", "HIGH"):
                    recent_risk_employees.append({
                        "name": emp.name,
                        "department": current_emp.department or "",
                        "position": current_emp.position or "",
                        "risk_level": risk_level,
                        "risk_reason": latest_risk.hr_comment or latest_risk.ai_risk_reasons or "",
                        "last_communication_date": None,
                    })

    return {
        "success": True,
        "data": {
            "metrics": {
                "active_employee_count": active_count,
                "probation_employee_count": probation_count,
                "regularization_due_7d_count": regularization_due_7d,
                "overdue_work_item_count": len(overdue_tasks) + len(overdue_todos),
            },
            "lifecycle_distribution": distribution,
            "priority_work_items": sorted(priority_items, key=lambda x: x["overdue_days"], reverse=True)[:8],
            "upcoming_events": [],
            "risk_employees": recent_risk_employees,
        },
        "request_id": str(uuid.uuid4()),
    }


@router.get("/work-items")
def get_work_items(
    keyword: str | None = Query(default=None, description="关键词搜索"),
    source_type: str | None = Query(default=None, description="类型：FOLLOWUP_TASK/TODO"),
    status: str | None = Query(default=None, description="状态"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """聚合工作事项：一次返回跟进任务和待办，包含员工信息。"""
    today = date.today()
    items = []

    # 1. 跟进任务
    tasks = []
    if source_type is None or source_type == "FOLLOWUP_TASK":
        task_query = (
            db.query(FollowupTask)
            .filter(FollowupTask.is_deleted == False)
        )
        if status:
            task_query = task_query.filter(FollowupTask.followup_status == status)
        tasks = task_query.order_by(FollowupTask.planned_date.asc()).all()

    # 批量获取任务对应的任职和员工信息
    task_emp_ids = set(t.employment_id for t in tasks)
    emp_records_map: dict[int, EmploymentRecord] = {}
    employees_map: dict[int, Employee] = {}
    if task_emp_ids:
        emp_recs = (
            db.query(EmploymentRecord)
            .filter(
                EmploymentRecord.id.in_(list(task_emp_ids)),
                EmploymentRecord.is_deleted == False,
            )
            .all()
        )
        for er in emp_recs:
            emp_records_map[er.id] = er
        emp_ids = set(er.employee_id for er in emp_recs)
        if emp_ids:
            emp_objs = (
                db.query(Employee)
                .filter(Employee.id.in_(list(emp_ids)), Employee.is_deleted == False)
                .all()
            )
            for eo in emp_objs:
                employees_map[eo.id] = eo

    # 批量获取风险等级
    task_risk_map: dict[int, str] = {}
    if task_emp_ids:
        task_risk_map = {
            employment_id: risk_level_value(risk)
            for employment_id, risk in latest_risks_by_employment(db, task_emp_ids).items()
        }

    for task in tasks:
        emp_rec = emp_records_map.get(task.employment_id)
        emp_name = ""
        dept = ""
        pos = ""
        emp_id = None
        risk_level = task_risk_map.get(task.employment_id, "NONE")
        if emp_rec:
            emp = employees_map.get(emp_rec.employee_id)
            if emp:
                emp_name = emp.name
                emp_id = emp.id
            dept = emp_rec.department or ""
            pos = emp_rec.position or ""

        planned = task.planned_date
        overdue = max(0, (today - planned).days) if planned and planned < today else 0
        days_until = (planned - today).days if planned else None

        items.append({
            "id": f"FOLLOWUP_TASK_{task.id}",
            "source_type": "FOLLOWUP_TASK",
            "source_id": task.id,
            "employee_id": emp_id,
            "employee_name": emp_name,
            "department": dept,
            "position": pos,
            "title": task.task_name,
            "due_at": str(planned) if planned else None,
            "status": _enum_value(task.followup_status),
            "risk_level": risk_level,
            "overdue_days": overdue,
            "days_until_due": days_until,
        })

    # 2. 待办
    if source_type is None or source_type == "TODO":
        todo_query = (
            db.query(SystemTodo)
        )
        if status:
            todo_query = todo_query.filter(SystemTodo.todo_status == status)
        todos = todo_query.order_by(SystemTodo.due_at.asc()).all()

        for todo in todos:
            due = todo.due_at
            overdue = max(0, (today - due).days) if due and due < today else 0
            days_until = (due - today).days if due else None
            items.append({
                "id": f"TODO_{todo.id}",
                "source_type": "TODO",
                "source_id": todo.id,
                "employee_id": None,
                "employee_name": "",
                "department": "",
                "position": "",
                "title": todo.title,
                "due_at": str(due) if due else None,
                "status": _enum_value(todo.todo_status),
                "risk_level": "NONE",
                "overdue_days": overdue,
                "days_until_due": days_until,
            })

    # 搜索过滤
    if keyword:
        kw = keyword.lower()
        items = [
            i for i in items
            if kw in i["title"].lower() or kw in i["employee_name"].lower()
        ]

    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items),
        },
        "request_id": str(uuid.uuid4()),
    }


@router.get("/probation/employees")
def get_probation_employees(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """试用期员工聚合信息（含跟进节点进度，N+1 优化版）。"""
    today = date.today()

    # 1. 一次性获取所有 PROBATION 生命周期的员工
    all_employees = (
        db.query(Employee)
        .filter(Employee.is_deleted == False)
        .all()
    )

    # 获取所有当前任职记录（每个员工一条）
    all_employments = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.is_deleted == False)
        .order_by(EmploymentRecord.employee_id, EmploymentRecord.employment_seq.desc())
        .all()
    )
    # 每个员工的最新 PENDING/ACTIVE/SEPARATING 任职
    emp_latest_employment: dict[int, EmploymentRecord] = {}
    for e in all_employments:
        if e.employee_id not in emp_latest_employment:
            if _enum_value(e.employment_status) in ("PENDING", "ACTIVE", "SEPARATING"):
                emp_latest_employment[e.employee_id] = e

    # 筛选试用期员工
    probation_emps = []
    for emp in all_employees:
        current_emp = emp_latest_employment.get(emp.id)
        stage = resolve_lifecycle_stage(current_emp) if current_emp else "UNKNOWN"
        if stage == "PROBATION" and current_emp:
            probation_emps.append((emp, current_emp))

    # 2. 批量获取这些员工的跟进任务
    probation_employment_ids = [ce.id for _, ce in probation_emps]
    all_tasks = {}
    if probation_employment_ids:
        tasks = (
            db.query(FollowupTask)
            .filter(
                FollowupTask.employment_id.in_(probation_employment_ids),
                FollowupTask.is_deleted == False,
            )
            .order_by(FollowupTask.planned_date.asc(), FollowupTask.id.asc())
            .all()
        )
        for t in tasks:
            all_tasks.setdefault(t.employment_id, []).append(t)

    # 3. 批量获取风险等级
    risk_map: dict[int, str] = {}
    if probation_employment_ids:
        risk_map = {
            employment_id: risk_level_value(risk)
            for employment_id, risk in latest_risks_by_employment(db, probation_employment_ids).items()
        }

    # 4. 构建响应
    items = []
    for emp, ce in probation_emps:
        tasks_for_emp = all_tasks.get(ce.id, [])
        total_count = len(tasks_for_emp)
        completed_tasks = [t for t in tasks_for_emp if t.followup_status == FollowupTaskStatus.COMPLETED]
        completed_count = len(completed_tasks)

        # 下一节点
        next_node = None
        active_tasks = [
            t for t in tasks_for_emp
            if t.followup_status in (
                FollowupTaskStatus.PENDING,
                FollowupTaskStatus.IN_PROGRESS,
                FollowupTaskStatus.PENDING_CONFIRMATION,
            )
        ]
        if active_tasks:
            next_task = active_tasks[0]  # 已按 planned_date ASC, id ASC 排序
            overdue_days = max(0, (today - next_task.planned_date).days) if next_task.planned_date and next_task.planned_date < today else 0
            days_until = (next_task.planned_date - today).days if next_task.planned_date else None
            next_node = {
                "task_id": next_task.id,
                "node_name": next_task.task_name,
                "planned_date": str(next_task.planned_date),
                "status": _enum_value(next_task.followup_status),
                "days_until_due": days_until,
                "overdue_days": overdue_days,
            }
        elif total_count > 0 and completed_count == total_count:
            next_node = {
                "task_id": None,
                "node_name": None,
                "planned_date": None,
                "status": "ALL_COMPLETED",
                "days_until_due": None,
                "overdue_days": 0,
            }
        else:
            next_node = {
                "task_id": None,
                "node_name": None,
                "planned_date": None,
                "status": "NO_TASKS",
                "days_until_due": None,
                "overdue_days": 0,
            }

        # 已完成节点详情
        completed_nodes = [
            {
                "task_id": t.id,
                "node_name": t.task_name,
                "completed_at": str(t.completed_at) if t.completed_at else None,
            }
            for t in completed_tasks
        ]

        # 全部节点详情（用于展开）
        all_nodes = [
            {
                "task_id": t.id,
                "node_name": t.task_name,
                "planned_date": str(t.planned_date) if t.planned_date else None,
                "status": _enum_value(t.followup_status),
                "completed_at": str(t.completed_at) if t.completed_at else None,
            }
            for t in tasks_for_emp
        ]

        item = {
            "employee_id": emp.id,
            "employee_name": emp.name,
            "department": ce.department or "",
            "position": ce.position or "",
            "hire_date": str(ce.hire_date),
            "employment_id": ce.id,
            "expected_regularization_date": str(ce.probation_end_date) if ce.probation_end_date else None,
            "probation_progress": _calc_probation_progress(ce.hire_date, ce.probation_end_date),
            "risk_level": risk_map.get(ce.id, "NONE"),
            "followup_progress": {
                "completed_count": completed_count,
                "total_count": total_count,
                "completed_nodes": completed_nodes,
                "all_nodes": all_nodes,
                "next_node": next_node,
            },
            "next_action": None,
        }
        items.append(item)

    # 分页
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return {
        "success": True,
        "data": {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "request_id": str(uuid.uuid4()),
    }


def _calc_probation_progress(hire_date: date | None, probation_end_date: date | None) -> float:
    """计算试用期进度 0.0~1.0。"""
    if not hire_date or not probation_end_date:
        return 0.0
    today = date.today()
    total_days = (probation_end_date - hire_date).days
    if total_days <= 0:
        return 1.0
    elapsed = (today - hire_date).days
    progress = elapsed / total_days
    return max(0.0, min(1.0, progress))


@router.get("/employee-movements")
def get_employee_movements(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """聚合异动记录：一次返回异动和离职记录，含员工信息。"""
    changes = []
    separations = []

    # 异动
    change_query = (
        db.query(EmploymentChange)
        .filter(EmploymentChange.is_deleted == False)
        .order_by(EmploymentChange.created_at.desc())
        .all()
    )
    for c in change_query:
        emp_rec = (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.id == c.employment_id, EmploymentRecord.is_deleted == False)
            .first()
        )
        emp_name = ""
        if emp_rec:
            emp = db.query(Employee).filter(Employee.id == emp_rec.employee_id, Employee.is_deleted == False).first()
            if emp:
                emp_name = emp.name
        changes.append({
            "id": c.id,
            "employee_name": emp_name,
            "employment_id": c.employment_id,
            "employee_id": emp_rec.employee_id if emp_rec else None,
            "change_type": c.change_type,
            "before_data": c.before_data,
            "after_data": c.after_data,
            "effective_date": str(c.effective_date) if c.effective_date else None,
            "reason": c.reason,
            "confirmed_by": c.confirmed_by,
            "confirmed_at": str(c.confirmed_at) if c.confirmed_at else None,
            "created_at": str(c.created_at) if c.created_at else None,
            "department": emp_rec.department if emp_rec else None,
            "position": emp_rec.position if emp_rec else None,
        })

    # 离职
    sep_query = (
        db.query(SeparationRecord)
        .filter(SeparationRecord.is_deleted == False)
        .order_by(SeparationRecord.created_at.desc())
        .all()
    )
    for s in sep_query:
        emp_rec = (
            db.query(EmploymentRecord)
            .filter(EmploymentRecord.id == s.employment_id, EmploymentRecord.is_deleted == False)
            .first()
        )
        emp_name = ""
        if emp_rec:
            emp = db.query(Employee).filter(Employee.id == emp_rec.employee_id, Employee.is_deleted == False).first()
            if emp:
                emp_name = emp.name
        separations.append({
            "id": s.id,
            "employee_name": emp_name,
            "employment_id": s.employment_id,
            "employee_id": emp_rec.employee_id if emp_rec else None,
            "separation_type": s.separation_type,
            "planned_separation_date": str(s.planned_separation_date) if s.planned_separation_date else None,
            "actual_separation_date": str(s.actual_separation_date) if s.actual_separation_date else None,
            "reason": s.reason,
            "hr_comment": s.hr_comment,
            "confirmed_by": s.confirmed_by,
            "confirmed_at": str(s.confirmed_at) if s.confirmed_at else None,
            "created_at": str(s.created_at) if s.created_at else None,
            "department": emp_rec.department if emp_rec else None,
            "position": emp_rec.position if emp_rec else None,
        })

    return {
        "success": True,
        "data": {
            "changes": changes,
            "separations": separations,
        },
        "request_id": str(uuid.uuid4()),
    }

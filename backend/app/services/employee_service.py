"""员工业务逻辑（参数使用 dict，返回 dict）。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..enums import EmployeeStatus, EmploymentStatus, ProbationStatus, FollowupTaskStatus, TodoStatus
from ..exceptions import (
    Conflict,
    ResourceDeleted,
    ResourceNotFound,
    ValidationError,
)
from ..models.employee import Employee
from ..models.employment import EmploymentRecord
from ..models.communication import CommunicationRecord
from ..models.risk import RiskAssessment
from ..models.followup_task import FollowupTask
from ..models.todo import SystemTodo
from .normalize import normalize_name
from .risk_query import latest_risks_by_employee, risk_level_value


def _get_active_employee(db: Session, employee_id: int) -> Employee:
    """查询未删除的员工，不存在时抛异常。"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ResourceNotFound("员工不存在")
    if emp.is_deleted:
        raise ResourceDeleted("员工已删除")
    return emp


def create_employee(db: Session, data: dict, operator: dict) -> dict:
    """创建员工。"""
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("员工姓名不能为空")

    normalized = normalize_name(name)

    employee_no = data.get("employee_no")
    # employee_no 非空时检查是否重复
    if employee_no:
        existing = (
            db.query(Employee)
            .filter(Employee.employee_no == employee_no, Employee.is_deleted == False)
            .first()
        )
        if existing:
            raise Conflict(f"员工编号 '{employee_no}' 已存在")

    emp = Employee(
        employee_no=employee_no,
        name=name,
        normalized_name=normalized,
        mobile=data.get("mobile"),
        email=data.get("email"),
        source=data.get("source"),
        employee_status=EmployeeStatus.ACTIVE,
        created_by=operator.get("user_id", "system"),
    )
    db.add(emp)
    db.flush()
    return emp.dict()


def update_employee(db: Session, employee_id: int, data: dict, operator: dict) -> dict:
    """更新员工信息。"""
    emp = _get_active_employee(db, employee_id)
    now = datetime.now()

    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise ValidationError("员工姓名不能为空")
        emp.name = name
        emp.normalized_name = normalize_name(name)

    if "employee_no" in data:
        # 检查新编号是否被其他员工占用
        new_no = data["employee_no"]
        if new_no:
            existing = (
                db.query(Employee)
                .filter(
                    Employee.employee_no == new_no,
                    Employee.id != employee_id,
                    Employee.is_deleted == False,
                )
                .first()
            )
            if existing:
                raise Conflict(f"员工编号 '{new_no}' 已被使用")
        emp.employee_no = new_no

    if "mobile" in data:
        emp.mobile = data["mobile"]
    if "email" in data:
        emp.email = data["email"]
    if "source" in data:
        emp.source = data["source"]

    emp.updated_by = operator.get("user_id", "system")
    emp.version = (emp.version or 0) + 1
    db.flush()
    return emp.dict()


def delete_employee(db: Session, employee_id: int, operator: dict) -> None:
    """逻辑删除员工。"""
    emp = _get_active_employee(db, employee_id)
    now = datetime.now()

    emp.is_deleted = True
    emp.deleted_by = operator.get("user_id", "system")
    db.flush()


def get_employee(db: Session, employee_id: int) -> Optional[dict]:
    """获取单个员工详情（含已删除）。"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        return None
    return emp.dict()


def _find_current_employment(db: Session, employee_id: int) -> Optional[EmploymentRecord]:
    """找到员工的当前有效任职（按创建时间倒序）。"""
    return (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.desc())
        .first()
    )


def resolve_lifecycle_stage(employment: Optional[EmploymentRecord]) -> str:
    """根据后端 enums 统一判断生命周期阶段。

    规则：
      没有当前任职 → UNKNOWN
      employment_status = PENDING → PENDING
      employment_status = SEPARATING → SEPARATING
      employment_status = SEPARATED → SEPARATED
      employment_status = ACTIVE:
        probation_status in (NOT_STARTED, IN_PROGRESS) → PROBATION
        probation_status = PENDING_REVIEW → REGULARIZATION_PENDING
        probation_status in (REGULARIZED, FAILED, TERMINATED) → ACTIVE
    """
    if not employment:
        return "UNKNOWN"
    es = employment.employment_status
    if es == EmploymentStatus.PENDING:
        return "PENDING"
    if es == EmploymentStatus.SEPARATING:
        return "SEPARATING"
    if es == EmploymentStatus.SEPARATED:
        return "SEPARATED"
    # es == ACTIVE
    ps = employment.probation_status
    if ps in (ProbationStatus.NOT_STARTED, ProbationStatus.IN_PROGRESS):
        return "PROBATION"
    if ps == ProbationStatus.PENDING_REVIEW:
        return "REGULARIZATION_PENDING"
    return "ACTIVE"


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _next_action_for_employee(
    db: Session, employee_id: int, current_emp: Optional[EmploymentRecord]
) -> Optional[dict]:
    """获取员工下一步行动事项。"""
    if not current_emp:
        return None
    now = datetime.now()
    today = now.date()

    # 1. 查询逾期跟进任务
    overdue_task = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.employment_id == current_emp.id,
            FollowupTask.is_deleted == False,
            FollowupTask.followup_status.in_(
                [FollowupTaskStatus.PENDING, FollowupTaskStatus.IN_PROGRESS]
            ),
            FollowupTask.planned_date < today,
        )
        .order_by(FollowupTask.planned_date.asc())
        .first()
    )
    if overdue_task:
        return {
            "id": overdue_task.id,
            "source_type": "FOLLOWUP_TASK",
            "title": overdue_task.task_name,
            "due_at": str(overdue_task.planned_date),
            "status": _enum_value(overdue_task.followup_status),
        }

    # 2. 查询待办
    pending_todo = (
        db.query(SystemTodo)
        .filter(
            SystemTodo.business_id.in_(
                db.query(EmploymentRecord.id)
                .filter(
                    EmploymentRecord.employee_id == employee_id,
                    EmploymentRecord.is_deleted == False,
                )
            ),
            SystemTodo.todo_status == TodoStatus.PENDING,
        )
        .order_by(SystemTodo.due_at.asc())
        .first()
    )
    if pending_todo:
        return {
            "id": pending_todo.id,
            "source_type": "TODO",
            "title": pending_todo.title,
            "due_at": str(pending_todo.due_at) if pending_todo.due_at else None,
            "status": pending_todo.todo_status,
        }

    # 3. 待转正
    if current_emp.probation_status == ProbationStatus.PENDING_REVIEW:
        return {
            "id": current_emp.id,
            "source_type": "REGULARIZATION",
            "title": "待转正审批",
            "due_at": str(current_emp.probation_end_date) if current_emp.probation_end_date else None,
            "status": "PENDING",
        }

    # 4. 待入职
    if current_emp.employment_status == EmploymentStatus.PENDING:
        return {
            "id": current_emp.id,
            "source_type": "PENDING_EMPLOYMENT",
            "title": "待入职",
            "due_at": str(current_emp.hire_date) if current_emp.hire_date else None,
            "status": "PENDING",
        }

    return None


def list_employees(db: Session, filters: dict) -> tuple[list[dict], int]:
    """
    分页查询员工列表。

    filters 支持：keyword, name, employee_no, employee_status,
                  lifecycle_stage, risk_level,
                  page, page_size, sort_by, sort_order
    """
    query = db.query(Employee).filter(Employee.is_deleted == False)

    keyword = filters.get("keyword")
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                Employee.name.like(like),
                Employee.employee_no.like(like),
                Employee.mobile.like(like),
                Employee.email.like(like),
            )
        )

    name_filter = filters.get("name")
    if name_filter:
        query = query.filter(Employee.normalized_name.like(f"%{normalize_name(name_filter)}%"))

    employee_no = filters.get("employee_no")
    if employee_no:
        query = query.filter(Employee.employee_no.like(f"%{employee_no}%"))

    status = filters.get("employee_status")
    if status:
        query = query.filter(Employee.employee_status == status)

    total = query.count()

    # 排序
    sort_by = filters.get("sort_by") or "id"
    sort_order = filters.get("sort_order") or "desc"
    sort_col = getattr(Employee, sort_by, Employee.id)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    page = filters.get("page", 1)
    page_size = filters.get("page_size", 20)
    offset = (page - 1) * page_size

    employees = query.offset(offset).limit(page_size).all()
    result = [e.dict() for e in employees]

    # 如果请求了 lifecycle_stage 或 risk_level 过滤或 include_employment，加载任职信息
    lifecycle_stage_filter = filters.get("lifecycle_stage")
    risk_level_filter = filters.get("risk_level")
    include_employment = filters.get("include_employment", False)

    if lifecycle_stage_filter or risk_level_filter or include_employment:
        enriched = []

        # 批量查询所有相关员工的最新风险（一次查询）
        emp_ids_in_result = [e["id"] for e in result]
        risk_map = {
            employee_id: risk_level_value(risk)
            for employee_id, risk in latest_risks_by_employee(db, emp_ids_in_result).items()
        }

        for emp_dict in result:
            emp_id = emp_dict["id"]
            current_emp = _find_current_employment(db, emp_id)
            stage = resolve_lifecycle_stage(current_emp) if current_emp else "UNKNOWN"

            # lifecycle_stage 过滤
            if lifecycle_stage_filter and stage != lifecycle_stage_filter:
                continue

            # risk_level 过滤（批量）
            if risk_level_filter:
                risk_level = risk_map.get(emp_id, "NONE")
                if risk_level_filter != risk_level:
                    continue
                emp_dict["risk_level"] = risk_level

            if include_employment and current_emp:
                emp_dict["current_employment"] = current_emp.dict()
                emp_dict["lifecycle_stage"] = stage
                emp_dict["next_action"] = _next_action_for_employee(db, emp_id, current_emp)

            enriched.append(emp_dict)
        result = enriched

    return result, total


def get_employee_timeline(db: Session, employee_id: int, limit: int = 10) -> dict:
    """获取员工完整时间线（后端统一聚合，不分页调用多个接口）。

    返回按 event_time DESC 排序的事件列表，每种业务事件使用真实发生时间。
    """
    from ..models.followup_task import FollowupTask
    from ..models.communication import CommunicationRecord
    from ..models.risk import RiskAssessment
    from ..models.ai_summary import AiSummaryVersion
    from ..models.probation import ProbationReview
    from ..models.regularization import RegularizationRecord
    from ..models.change import EmploymentChange
    from ..models.separation import SeparationRecord

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ResourceNotFound("员工不存在")

    all_events: list[dict] = []

    # 1. 创建员工档案
    if emp.created_at:
        all_events.append({
            "id": f"EMPLOYEE_CREATED_{emp.id}",
            "event_type": "EMPLOYEE_CREATED",
            "event_name": "创建员工档案",
            "event_time": emp.created_at.isoformat() if hasattr(emp.created_at, "isoformat") else str(emp.created_at),
            "employee_id": emp.id,
            "employment_id": None,
            "source_id": emp.id,
            "source_type": "EMPLOYEE",
            "title": "创建员工档案",
            "summary": f"员工 {emp.name} 档案创建",
            "operator_name": emp.created_by or "system",
            "metadata": {},
        })

    # 查询该员工的全部任职
    employments = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.asc())
        .all()
    )

    employment_ids = [e.id for e in employments]

    for emp_rec in employments:
        # 2. 创建任职记录；第 2 次及以后用再次入职表达业务含义
        if emp_rec.created_at:
            is_reemployment = (emp_rec.employment_seq or 1) > 1
            event_type = "REEMPLOYMENT_CREATED" if is_reemployment else "EMPLOYMENT_CREATED"
            event_name = "再次入职" if is_reemployment else f"第 {emp_rec.employment_seq} 次任职"
            all_events.append({
                "id": f"{event_type}_{emp_rec.id}",
                "event_type": event_type,
                "event_name": event_name,
                "event_time": emp_rec.created_at.isoformat() if hasattr(emp_rec.created_at, "isoformat") else str(emp_rec.created_at),
                "employee_id": employee_id,
                "employment_id": emp_rec.id,
                "source_id": emp_rec.id,
                "source_type": "EMPLOYMENT",
                "title": f"创建任职记录",
                "summary": f"任职部门: {emp_rec.department or '—'}, 岗位: {emp_rec.position or '—'}, 状态: {emp_rec.employment_status}",
                "operator_name": emp_rec.created_by or "system",
                "metadata": {
                    "department": emp_rec.department,
                    "position": emp_rec.position,
                    "employment_status": emp_rec.employment_status,
                },
            })

        # 3. 正式入职（hire_date）
        if emp_rec.hire_date and emp_rec.employment_status in (EmploymentStatus.ACTIVE, EmploymentStatus.SEPARATING, EmploymentStatus.SEPARATED):
            hire_dt = datetime.combine(emp_rec.hire_date, datetime.min.time())
            all_events.append({
                "id": f"EMPLOYMENT_STARTED_{emp_rec.id}",
                "event_type": "EMPLOYMENT_STARTED",
                "event_name": "正式入职",
                "event_time": hire_dt.isoformat(),
                "employee_id": employee_id,
                "employment_id": emp_rec.id,
                "source_id": emp_rec.id,
                "source_type": "EMPLOYMENT",
                "title": "正式入职",
                "summary": f"员工于 {emp_rec.hire_date} 正式入职 {emp_rec.department or '—'} 担任 {emp_rec.position or '—'}",
                "operator_name": emp_rec.created_by or "system",
                "metadata": {
                    "department": emp_rec.department,
                    "position": emp_rec.position,
                    "hire_date": str(emp_rec.hire_date),
                },
            })

    # 4. 跟进任务事件
    if employment_ids:
        followup_tasks = (
            db.query(FollowupTask)
            .filter(
                FollowupTask.employment_id.in_(employment_ids),
                FollowupTask.is_deleted == False,
            )
            .all()
        )
        for ft in followup_tasks:
            # 创建跟进任务
            if ft.created_at:
                all_events.append({
                    "id": f"FOLLOWUP_TASK_CREATED_{ft.id}",
                    "event_type": "FOLLOWUP_TASK_CREATED",
                    "event_name": f"创建跟进任务",
                    "event_time": ft.created_at.isoformat() if hasattr(ft.created_at, "isoformat") else str(ft.created_at),
                    "employee_id": employee_id,
                    "employment_id": ft.employment_id,
                    "source_id": ft.id,
                    "source_type": "FOLLOWUP_TASK",
                    "title": ft.task_name,
                    "summary": f"创建跟进任务: {ft.task_name}",
                    "operator_name": ft.created_by or "system",
                    "metadata": {
                        "task_name": ft.task_name,
                        "planned_date": str(ft.planned_date) if ft.planned_date else None,
                        "node_code": ft.node_code_snapshot,
                    },
                })
            # 开始处理
            if ft.followup_status in (FollowupTaskStatus.IN_PROGRESS, FollowupTaskStatus.PENDING_CONFIRMATION, FollowupTaskStatus.COMPLETED):
                event_time = ft.updated_at or ft.created_at
                if event_time:
                    all_events.append({
                        "id": f"FOLLOWUP_TASK_STARTED_{ft.id}",
                        "event_type": "FOLLOWUP_TASK_STARTED",
                        "event_name": f"开始跟进",
                        "event_time": event_time.isoformat() if hasattr(event_time, "isoformat") else str(event_time),
                        "employee_id": employee_id,
                        "employment_id": ft.employment_id,
                        "source_id": ft.id,
                        "source_type": "FOLLOWUP_TASK",
                        "title": ft.task_name,
                        "summary": f"开始跟进任务: {ft.task_name}",
                        "operator_name": ft.updated_by or ft.created_by or "system",
                        "metadata": {
                            "task_name": ft.task_name,
                            "planned_date": str(ft.planned_date) if ft.planned_date else None,
                        },
                    })
            # 提交确认
            if ft.followup_status in (FollowupTaskStatus.PENDING_CONFIRMATION, FollowupTaskStatus.COMPLETED):
                conf_event_time = ft.updated_at or ft.created_at
                if conf_event_time:
                    all_events.append({
                        "id": f"FOLLOWUP_TASK_SUBMITTED_{ft.id}",
                        "event_type": "FOLLOWUP_TASK_SUBMITTED",
                        "event_name": f"跟进已提交",
                        "event_time": conf_event_time.isoformat() if hasattr(conf_event_time, "isoformat") else str(conf_event_time),
                        "employee_id": employee_id,
                        "employment_id": ft.employment_id,
                        "source_id": ft.id,
                        "source_type": "FOLLOWUP_TASK",
                        "title": ft.task_name,
                        "summary": f"跟进任务已提交确认: {ft.task_name}",
                        "operator_name": ft.updated_by or ft.created_by or "system",
                        "metadata": {
                            "task_name": ft.task_name,
                        },
                    })
            # 已完成
            if ft.followup_status == FollowupTaskStatus.COMPLETED:
                complete_time = ft.completed_at or ft.updated_at
                if complete_time:
                    all_events.append({
                        "id": f"FOLLOWUP_TASK_COMPLETED_{ft.id}",
                        "event_type": "FOLLOWUP_TASK_COMPLETED",
                        "event_name": f"跟进已完成",
                        "event_time": complete_time.isoformat() if hasattr(complete_time, "isoformat") else str(complete_time),
                        "employee_id": employee_id,
                        "employment_id": ft.employment_id,
                        "source_id": ft.id,
                        "source_type": "FOLLOWUP_TASK",
                        "title": ft.task_name,
                        "summary": f"完成跟进任务: {ft.task_name}",
                        "operator_name": ft.completed_by or ft.updated_by or ft.created_by or "system",
                        "metadata": {
                            "task_name": ft.task_name,
                        },
                    })
            # 已取消
            if ft.followup_status == FollowupTaskStatus.CANCELLED:
                cancel_time = ft.updated_at or ft.created_at
                if cancel_time:
                    all_events.append({
                        "id": f"FOLLOWUP_TASK_CANCELLED_{ft.id}",
                        "event_type": "FOLLOWUP_TASK_CANCELLED",
                        "event_name": f"跟进已取消",
                        "event_time": cancel_time.isoformat() if hasattr(cancel_time, "isoformat") else str(cancel_time),
                        "employee_id": employee_id,
                        "employment_id": ft.employment_id,
                        "source_id": ft.id,
                        "source_type": "FOLLOWUP_TASK",
                        "title": ft.task_name,
                        "summary": f"取消跟进任务: {ft.task_name}",
                        "operator_name": ft.updated_by or ft.created_by or "system",
                        "metadata": {
                            "task_name": ft.task_name,
                            "cancel_reason": ft.cancel_reason,
                        },
                    })

        # 5. 沟通记录
        communications = (
            db.query(CommunicationRecord)
            .filter(
                CommunicationRecord.employment_id.in_(employment_ids),
                CommunicationRecord.is_deleted == False,
            )
            .all()
        )
        comm_ids = [c.id for c in communications]
        latest_risk_by_comm: dict[int, RiskAssessment] = {}
        if comm_ids:
            risk_rows = (
                db.query(RiskAssessment)
                .filter(
                    RiskAssessment.communication_id.in_(comm_ids),
                    RiskAssessment.is_current == True,
                    RiskAssessment.is_deleted == False,
                )
                .order_by(
                    RiskAssessment.communication_id.asc(),
                    RiskAssessment.created_at.desc(),
                    RiskAssessment.id.desc(),
                )
                .all()
            )
            for risk in risk_rows:
                latest_risk_by_comm.setdefault(risk.communication_id, risk)

        for comm in communications:
            event_time = comm.communication_at or comm.created_at
            if event_time:
                risk_level = risk_level_value(latest_risk_by_comm.get(comm.id))
                if risk_level == "NONE":
                    risk_level = None

                all_events.append({
                    "id": f"COMMUNICATION_CREATED_{comm.id}",
                    "event_type": "COMMUNICATION_CREATED",
                    "event_name": "新增沟通记录",
                    "event_time": event_time.isoformat() if hasattr(event_time, "isoformat") else str(event_time),
                    "employee_id": employee_id,
                    "employment_id": comm.employment_id,
                    "source_id": comm.id,
                    "source_type": "COMMUNICATION",
                    "title": "新增沟通记录",
                    "summary": comm.manual_summary or f"沟通类型: {comm.communication_type or '一般沟通'}",
                    "operator_name": comm.hr_user_id or comm.created_by or "system",
                    "metadata": {
                        "communication_type": comm.communication_type,
                        "risk_level": risk_level,
                        "hr_conclusion": comm.hr_conclusion,
                    },
                })

            # 6. AI 总结完成
            ai_summaries = (
                db.query(AiSummaryVersion)
                .filter(
                    AiSummaryVersion.communication_id == comm.id,
                    AiSummaryVersion.summary_status == "SUCCEEDED",
                )
                .order_by(AiSummaryVersion.finished_at.asc())
                .all()
            )
            for ai in ai_summaries:
                ai_time = ai.finished_at or ai.updated_at or ai.created_at
                if ai_time:
                    all_events.append({
                        "id": f"AI_SUMMARY_COMPLETED_{ai.id}",
                        "event_type": "AI_SUMMARY_COMPLETED",
                        "event_name": "AI 总结完成",
                        "event_time": ai_time.isoformat() if hasattr(ai_time, "isoformat") else str(ai_time),
                        "employee_id": employee_id,
                        "employment_id": comm.employment_id,
                        "source_id": ai.id,
                        "source_type": "AI_SUMMARY",
                        "title": "AI 总结完成",
                        "summary": f"AI 对沟通内容进行了分析总结",
                        "operator_name": ai.created_by or "system",
                        "metadata": {
                            "provider": ai.provider,
                            "model_name": ai.model_name,
                            "is_current": ai.is_current,
                        },
                    })

            # 7. 风险评估结果
            risks = (
                db.query(RiskAssessment)
                .filter(
                    RiskAssessment.communication_id == comm.id,
                    RiskAssessment.is_deleted == False,
                )
                .order_by(RiskAssessment.created_at.asc(), RiskAssessment.id.asc())
                .all()
            )
            for risk in risks:
                risk_time = risk.created_at
                if risk_time:
                    risk_level = risk_level_value(risk)
                    if risk_level == "NONE":
                        risk_level = "UNSPECIFIED"
                    level_label = {"HIGH": "高风险", "MEDIUM": "需关注", "LOW": "低风险", "UNSPECIFIED": "未评估"}.get(risk_level, risk_level)
                    all_events.append({
                        "id": f"RISK_LEVEL_CHANGED_{risk.id}",
                        "event_type": "RISK_LEVEL_CHANGED",
                        "event_name": "风险等级变化",
                        "event_time": risk_time.isoformat() if hasattr(risk_time, "isoformat") else str(risk_time),
                        "employee_id": employee_id,
                        "employment_id": comm.employment_id,
                        "source_id": risk.id,
                        "source_type": "RISK",
                        "title": "风险等级变化",
                        "summary": f"风险评估等级: {level_label}",
                        "operator_name": risk.reviewed_by or risk.created_by or "system",
                        "metadata": {
                            "risk_level": risk_level,
                            "ai_risk_level": risk.ai_risk_level,
                            "hr_risk_level": risk.hr_risk_level,
                            "risk_review_status": risk.risk_review_status,
                            "risk_reasons": risk.ai_risk_reasons or risk.hr_comment,
                        },
                    })

        # 8. 试用期评估
        prob_reviews = (
            db.query(ProbationReview)
            .filter(
                ProbationReview.employment_id.in_(employment_ids),
                ProbationReview.is_deleted == False,
            )
            .order_by(ProbationReview.review_seq.asc())
            .all()
        )
        for pr in prob_reviews:
            # 创建评估
            if pr.created_at:
                all_events.append({
                    "id": f"PROBATION_REVIEW_CREATED_{pr.id}",
                    "event_type": "PROBATION_REVIEW_CREATED",
                    "event_name": "新增试用期评估",
                    "event_time": pr.created_at.isoformat() if hasattr(pr.created_at, "isoformat") else str(pr.created_at),
                    "employee_id": employee_id,
                    "employment_id": pr.employment_id,
                    "source_id": pr.id,
                    "source_type": "PROBATION",
                    "title": f"{'过程评估' if pr.review_stage == 'FOLLOWUP' else '最终评估'}第{pr.review_seq}次",
                    "summary": pr.hr_evaluation or f"评估完成，建议: {pr.recommendation or '—'}",
                    "operator_name": pr.reviewed_by or pr.created_by or "system",
                    "metadata": {
                        "review_stage": pr.review_stage,
                        "review_seq": pr.review_seq,
                        "recommendation": pr.recommendation,
                    },
                })
            # 更新评估
            if pr.updated_at and pr.updated_at != pr.created_at:
                all_events.append({
                    "id": f"PROBATION_REVIEW_UPDATED_{pr.id}",
                    "event_type": "PROBATION_REVIEW_UPDATED",
                    "event_name": "更新试用期评估",
                    "event_time": pr.updated_at.isoformat() if hasattr(pr.updated_at, "isoformat") else str(pr.updated_at),
                    "employee_id": employee_id,
                    "employment_id": pr.employment_id,
                    "source_id": pr.id,
                    "source_type": "PROBATION",
                    "title": f"更新评估",
                    "summary": "试用期评估内容已更新",
                    "operator_name": pr.updated_by or pr.created_by or "system",
                    "metadata": {
                        "review_stage": pr.review_stage,
                        "review_seq": pr.review_seq,
                    },
                })

        # 9. 转正
        reg_records = (
            db.query(RegularizationRecord)
            .filter(
                RegularizationRecord.employment_id.in_(employment_ids),
                RegularizationRecord.is_deleted == False,
            )
            .order_by(RegularizationRecord.created_at.asc())
            .all()
        )
        for reg in reg_records:
            # 发起转正
            if reg.created_at:
                all_events.append({
                    "id": f"REGULARIZATION_STARTED_{reg.id}",
                    "event_type": "REGULARIZATION_STARTED",
                    "event_name": "发起转正",
                    "event_time": reg.created_at.isoformat() if hasattr(reg.created_at, "isoformat") else str(reg.created_at),
                    "employee_id": employee_id,
                    "employment_id": reg.employment_id,
                    "source_id": reg.id,
                    "source_type": "REGULARIZATION",
                    "title": "发起转正",
                    "summary": f"转正决策: {reg.decision}",
                    "operator_name": reg.confirmed_by or reg.created_by or "system",
                    "metadata": {
                        "decision": reg.decision,
                        "effective_date": str(reg.effective_date) if reg.effective_date else None,
                    },
                })
            # 完成转正（基于 effective_date）
            if reg.effective_date and reg.decision == "APPROVED":
                eff_dt = datetime.combine(reg.effective_date, datetime.min.time())
                all_events.append({
                    "id": f"REGULARIZATION_COMPLETED_{reg.id}",
                    "event_type": "REGULARIZATION_COMPLETED",
                    "event_name": "完成转正",
                    "event_time": eff_dt.isoformat(),
                    "employee_id": employee_id,
                    "employment_id": reg.employment_id,
                    "source_id": reg.id,
                    "source_type": "REGULARIZATION",
                    "title": "完成转正",
                    "summary": f"员工于 {reg.effective_date} 完成转正",
                    "operator_name": reg.confirmed_by or "system",
                    "metadata": {
                        "decision": reg.decision,
                        "effective_date": str(reg.effective_date),
                    },
                })
            elif reg.effective_date and reg.decision == "EXTENDED":
                eff_dt = datetime.combine(reg.effective_date, datetime.min.time())
                all_events.append({
                    "id": f"REGULARIZATION_EXTENDED_{reg.id}",
                    "event_type": "REGULARIZATION_EXTENDED",
                    "event_name": "延长试用期",
                    "event_time": eff_dt.isoformat(),
                    "employee_id": employee_id,
                    "employment_id": reg.employment_id,
                    "source_id": reg.id,
                    "source_type": "REGULARIZATION",
                    "title": "延长试用期",
                    "summary": f"试用期延长至 {reg.new_probation_end_date}",
                    "operator_name": reg.confirmed_by or "system",
                    "metadata": {
                        "decision": reg.decision,
                        "new_probation_end_date": str(reg.new_probation_end_date) if reg.new_probation_end_date else None,
                    },
                })

        # 10. 任职异动
        changes = (
            db.query(EmploymentChange)
            .filter(
                EmploymentChange.employment_id.in_(employment_ids),
                EmploymentChange.is_deleted == False,
            )
            .order_by(EmploymentChange.effective_date.asc())
            .all()
        )
        for ch in changes:
            ch_time = ch.confirmed_at or ch.created_at
            if ch_time:
                change_type_labels = {
                    "DEPARTMENT": "部门变更",
                    "POSITION": "岗位变更",
                    "MANAGER": "负责人变更",
                }
                ct_label = change_type_labels.get(ch.change_type, ch.change_type)
                before = json.loads(ch.before_data) if ch.before_data else {}
                after = json.loads(ch.after_data) if ch.after_data else {}
                all_events.append({
                    "id": f"EMPLOYMENT_CHANGED_{ch.id}",
                    "event_type": "EMPLOYMENT_CHANGED",
                    "event_name": ct_label,
                    "event_time": ch_time.isoformat() if hasattr(ch_time, "isoformat") else str(ch_time),
                    "employee_id": employee_id,
                    "employment_id": ch.employment_id,
                    "source_id": ch.id,
                    "source_type": "CHANGE",
                    "title": ct_label,
                    "summary": f"变更类型: {ct_label}, 原因: {ch.reason or '—'}",
                    "operator_name": ch.confirmed_by or ch.created_by or "system",
                    "metadata": {
                        "change_type": ch.change_type,
                        "effective_date": str(ch.effective_date) if ch.effective_date else None,
                        "before": before,
                        "after": after,
                        "reason": ch.reason,
                    },
                })

        # 11. 离职
        seps = (
            db.query(SeparationRecord)
            .filter(
                SeparationRecord.employment_id.in_(employment_ids),
                SeparationRecord.is_deleted == False,
            )
            .order_by(SeparationRecord.created_at.asc())
            .all()
        )
        for sep in seps:
            # 启动离职
            if sep.created_at:
                all_events.append({
                    "id": f"SEPARATION_STARTED_{sep.id}",
                    "event_type": "SEPARATION_STARTED",
                    "event_name": "启动离职",
                    "event_time": sep.created_at.isoformat() if hasattr(sep.created_at, "isoformat") else str(sep.created_at),
                    "employee_id": employee_id,
                    "employment_id": sep.employment_id,
                    "source_id": sep.id,
                    "source_type": "SEPARATION",
                    "title": "启动离职",
                    "summary": f"离职类型: {sep.separation_type or '—'}, 原因: {sep.reason or '—'}",
                    "operator_name": sep.created_by or "system",
                    "metadata": {
                        "separation_type": sep.separation_type,
                        "reason": sep.reason,
                    },
                })
            # 确认离职
            if sep.confirmed_at or sep.actual_separation_date:
                confirm_time = sep.confirmed_at
                if not confirm_time and sep.actual_separation_date:
                    confirm_time = datetime.combine(sep.actual_separation_date, datetime.min.time())
                if confirm_time:
                    all_events.append({
                        "id": f"SEPARATION_COMPLETED_{sep.id}",
                        "event_type": "SEPARATION_COMPLETED",
                        "event_name": "确认离职",
                        "event_time": confirm_time.isoformat() if hasattr(confirm_time, "isoformat") else str(confirm_time),
                        "employee_id": employee_id,
                        "employment_id": sep.employment_id,
                        "source_id": sep.id,
                        "source_type": "SEPARATION",
                        "title": "确认离职",
                        "summary": f"确认离职, 实际离职日: {sep.actual_separation_date or '—'}",
                        "operator_name": sep.confirmed_by or sep.created_by or "system",
                        "metadata": {
                            "separation_type": sep.separation_type,
                            "actual_separation_date": str(sep.actual_separation_date) if sep.actual_separation_date else None,
                            "hr_comment": sep.hr_comment,
                        },
                    })

    # 按 event_time DESC 排序，相同时按类型优先级
    priority_order = {
        "EMPLOYEE_CREATED": 0,
        "EMPLOYMENT_STARTED": 1,
        "EMPLOYMENT_CREATED": 2,
        "REEMPLOYMENT_CREATED": 2,
        "REGULARIZATION_COMPLETED": 3,
        "REGULARIZATION_EXTENDED": 3,
        "REGULARIZATION_STARTED": 4,
        "SEPARATION_COMPLETED": 5,
        "SEPARATION_STARTED": 6,
        "FOLLOWUP_TASK_COMPLETED": 7,
        "FOLLOWUP_TASK_CANCELLED": 7,
        "FOLLOWUP_TASK_SUBMITTED": 8,
        "FOLLOWUP_TASK_STARTED": 9,
        "FOLLOWUP_TASK_CREATED": 10,
        "PROBATION_REVIEW_CREATED": 11,
        "PROBATION_REVIEW_UPDATED": 12,
        "RISK_LEVEL_CHANGED": 13,
        "COMMUNICATION_CREATED": 14,
        "AI_SUMMARY_COMPLETED": 15,
        "EMPLOYMENT_CHANGED": 16,
    }

    all_events.sort(
        key=lambda e: (
            e.get("event_time", ""),
            -priority_order.get(e.get("event_type", ""), 99),
            e.get("id", ""),
        ),
        reverse=True,
    )

    total = len(all_events)
    limited = all_events[:limit]

    return {
        "items": limited,
        "total": total,
    }

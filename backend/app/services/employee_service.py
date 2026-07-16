"""员工业务逻辑（参数使用 dict，返回 dict）。"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..enums import (
    ConfirmationItemStatus,
    EmployeeStatus,
    EmploymentStatus,
    FollowupTaskStatus,
    ProbationStatus,
    TodoStatus,
)

logger = logging.getLogger(__name__)
from ..exceptions import (
    Conflict,
    ResourceDeleted,
    ResourceNotFound,
    ValidationError,
)
from ..models.employee import Employee
from ..models.employee_profile import EmployeeProfile
from ..models.employment import EmploymentRecord
from ..models.contract import EmploymentContract
from ..models.risk import RiskAssessment
from ..models.followup_task import FollowupTask
from ..models.todo import SystemTodo
from ..models.hr_confirmation import HrConfirmationItem
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

    # 检查同名员工（正常、未删除员工不能重名）
    existing_same_name = (
        db.query(Employee)
        .filter(
            Employee.normalized_name == normalized,
            Employee.is_deleted == False,
            Employee.employee_status != EmployeeStatus.ENTRY_ERROR,
        )
        .first()
    )
    if existing_same_name:
        raise Conflict(f"已存在同名员工 '{name}'，不允许重复创建")

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
    """更新员工信息。

    注意：姓名（name）不允许通过普通更新接口修改。
    需要修改姓名时，走专门的姓名纠错流程。
    """
    emp = _get_active_employee(db, employee_id)
    now = datetime.now()

    if "name" in data and data["name"] is not None:
        # 如果新名称与原名称相同（标准化后），允许
        new_name = data["name"].strip()
        new_normalized = normalize_name(new_name)
        if new_normalized != emp.normalized_name:
            raise ValidationError("员工姓名不允许通过普通更新接口修改。如需修改姓名，请使用专门的姓名纠错流程。")

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


# ============================================================
# 批量查询辅助函数 — 消除 N+1
# ============================================================


def _find_current_employment(db: Session, employee_id: int) -> Optional[EmploymentRecord]:
    """找到员工的当前有效任职。

    选择规则：
      优先 PENDING / ACTIVE / SEPARATING 状态的有效任职。
      同一员工最多一条 PENDING / ACTIVE / SEPARATING 的有效任职（数据库约束）。
      如果有多条，取 employment_seq 最大的一条。
    """
    return (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
            EmploymentRecord.employment_status.in_(
                [EmploymentStatus.PENDING, EmploymentStatus.ACTIVE, EmploymentStatus.SEPARATING]
            ),
        )
        .order_by(EmploymentRecord.employment_seq.desc())
        .first()
    )


def _batch_current_employments(
    db: Session, employee_ids: list[int]
) -> dict[int, Optional[EmploymentRecord]]:
    """批量查询所有员工的当前任职。"""
    if not employee_ids:
        return {}
    employments = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id.in_(employee_ids),
            EmploymentRecord.is_deleted == False,
            EmploymentRecord.employment_status.in_(
                [EmploymentStatus.PENDING, EmploymentStatus.ACTIVE, EmploymentStatus.SEPARATING]
            ),
        )
        .order_by(EmploymentRecord.employee_id, EmploymentRecord.employment_seq.desc())
        .all()
    )
    result: dict[int, Optional[EmploymentRecord]] = {}
    # 每个 employee_id 只保留 employment_seq 最大的那条
    for emp_rec in employments:
        if emp_rec.employee_id not in result:
            result[emp_rec.employee_id] = emp_rec
    return result


def _batch_profiles(
    db: Session, employee_ids: list[int]
) -> dict[int, EmployeeProfile]:
    """批量查询员工档案（含身份证号、性别、出生日期、社保公积金状态）。"""
    if not employee_ids:
        return {}
    profiles = (
        db.query(EmployeeProfile)
        .filter(
            EmployeeProfile.employee_id.in_(employee_ids),
        )
        .all()
    )
    return {p.employee_id: p for p in profiles}


def _batch_contracts(
    db: Session, employee_ids: list[int]
) -> dict[int, list[EmploymentContract]]:
    """批量查询员工合同，按 employee_id 分组。"""
    if not employee_ids:
        return {}
    contracts = (
        db.query(EmploymentContract)
        .filter(
            EmploymentContract.employee_id.in_(employee_ids),
            EmploymentContract.is_deleted == False,
        )
        .order_by(EmploymentContract.id.desc())
        .all()
    )
    result: dict[int, list[EmploymentContract]] = {}
    for c in contracts:
        result.setdefault(c.employee_id, []).append(c)
    return result


def _batch_pending_tasks(
    db: Session, employment_ids: list[int]
) -> dict[int, list[FollowupTask]]:
    """批量查询待处理跟进任务，按 employment_id 分组。"""
    if not employment_ids:
        return {}
    tasks = (
        db.query(FollowupTask)
        .filter(
            FollowupTask.employment_id.in_(employment_ids),
            FollowupTask.is_deleted == False,
            FollowupTask.followup_status.in_(
                [FollowupTaskStatus.PENDING, FollowupTaskStatus.IN_PROGRESS]
            ),
        )
        .order_by(FollowupTask.planned_date.asc(), FollowupTask.id.asc())
        .all()
    )
    result: dict[int, list[FollowupTask]] = {}
    for t in tasks:
        result.setdefault(t.employment_id, []).append(t)
    return result


def _batch_pending_hr_confirmations(
    db: Session, employee_ids: list[int]
) -> dict[int, list[HrConfirmationItem]]:
    """批量查询待 HR 确认事项，按 employee_id 分组。"""
    if not employee_ids:
        return {}
    items = (
        db.query(HrConfirmationItem)
        .filter(
            HrConfirmationItem.employee_id.in_(employee_ids),
            HrConfirmationItem.item_status == ConfirmationItemStatus.PENDING,
        )
        .order_by(HrConfirmationItem.created_at.asc())
        .all()
    )
    result: dict[int, list[HrConfirmationItem]] = {}
    for item in items:
        result.setdefault(item.employee_id, []).append(item)
    return result


# ============================================================
# 生命周期阶段判断
# ============================================================


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


def _str_date(d: Optional[date | datetime]) -> Optional[str]:
    """将 date/datetime 转为 YYYY-MM-DD 字符串。"""
    if not d:
        return None
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    return d.isoformat()


# ============================================================
# 年龄计算
# ============================================================


def _parse_birth_date_from_id_card(id_card: str) -> Optional[date]:
    """从身份证号码中提取出生日期。

    支持 18 位和 15 位身份证。
    """
    if not id_card:
        return None
    card = id_card.strip().upper()
    # 18 位：YYYYMMDD
    if len(card) == 18:
        y_str, m_str, d_str = card[6:10], card[10:12], card[12:14]
    # 15 位：YYMMDD，年份补 19
    elif len(card) == 15:
        y_str, m_str, d_str = f"19{card[6:8]}", card[8:10], card[10:12]
    else:
        return None

    if not (y_str.isdigit() and m_str.isdigit() and d_str.isdigit()):
        return None
    try:
        return date(int(y_str), int(m_str), int(d_str))
    except (ValueError, OverflowError):
        return None


def _calculate_age(birth: date, reference: Optional[date] = None) -> int:
    """根据出生日期和参考日期计算年龄，参考日期默认当天。

    必须判断今年生日是否已经到达。
    """
    if reference is None:
        reference = date.today()
    age = reference.year - birth.year
    # 如果今年生日还没到，减 1
    if (reference.month, reference.day) < (birth.month, birth.day):
        age -= 1
    return age


def _resolve_birth_date_and_age(
    profile: Optional[EmployeeProfile],
) -> tuple[Optional[date], Optional[int]]:
    """从 profile 中解析出生日期和年龄。

    优先级：
      1. 从有效身份证号码中提取出生日期
      2. 身份证无法解析时，使用员工档案中的 birth_date
      3. 两者都没有时返回 (None, None)
    """
    birth: Optional[date] = None

    if profile:
        # 优先从身份证提取
        if profile.identity_card:
            birth = _parse_birth_date_from_id_card(profile.identity_card)
        # 回退到 birth_date
        if birth is None and profile.birth_date:
            birth = profile.birth_date

    age = _calculate_age(birth) if birth else None
    return birth, age


# ============================================================
# 试用期进度计算
# ============================================================


def _calc_probation_progress(
    emp_rec: EmploymentRecord,
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
    """计算试用期进度。

    Returns:
        (probation_progress, days_remaining, overdue_days, expected_regularization_date_str)
    """
    hire = emp_rec.actual_hire_date or emp_rec.hire_date
    prob_end = emp_rec.probation_end_date or emp_rec.expected_regularization_date
    today = date.today()

    if not hire or not prob_end:
        return None, None, None, None

    if isinstance(hire, datetime):
        hire = hire.date()
    if isinstance(prob_end, datetime):
        prob_end = prob_end.date()

    total_days = (prob_end - hire).days
    if total_days <= 0:
        return 100, 0, 0, _str_date(prob_end)

    elapsed = (today - hire).days
    progress = min(100, max(0, round(elapsed / total_days * 100)))

    if today > prob_end:
        overdue_days = (today - prob_end).days
        days_remaining = 0
    else:
        overdue_days = 0
        days_remaining = (prob_end - today).days

    return progress, days_remaining, overdue_days, _str_date(prob_end)


# ============================================================
# 司龄计算
# ============================================================


def _calc_tenure(hire_date_val: Optional[date], reference: Optional[date] = None) -> Optional[str]:
    """计算司龄文本。

    格式：X年X个月 或 X天
    """
    if not hire_date_val:
        return None
    if isinstance(hire_date_val, datetime):
        hire_date_val = hire_date_val.date()
    if reference is None:
        reference = date.today()

    if hire_date_val > reference:
        return "0天"

    total_days = (reference - hire_date_val).days
    years = total_days // 365
    remaining_days = total_days % 365
    months = remaining_days // 30
    days = remaining_days % 30

    parts = []
    if years > 0:
        parts.append(f"{years}年")
    if months > 0:
        parts.append(f"{months}个月")
    if years == 0 and months == 0:
        parts.append(f"{days}天")
    elif days > 0:
        parts.append(f"{days}天")

    return "".join(parts) if parts else "0天"


# ============================================================
# 下一事项
# ============================================================


def _calc_days_until(due_date: date | datetime | None) -> tuple[Optional[int], int]:
    """计算 days_until_due（可为负）和 overdue_days（仅正数）。"""
    if not due_date:
        return None, 0
    if isinstance(due_date, datetime):
        due_date = due_date.date()
    today = date.today()
    delta = (due_date - today).days
    overdue = max(0, -delta) if delta < 0 else 0
    return delta, overdue


def _build_next_action_for_employee(
    db: Session,
    employee_id: int,
    current_emp: Optional[EmploymentRecord],
    pending_tasks_by_employment: dict[int, list[FollowupTask]],
    pending_confirmations_by_employee: dict[int, list[HrConfirmationItem]],
    employment_ids_for_todos: list[int],
) -> Optional[dict]:
    """获取员工下一步行动事项，返回已排序的最近一条。

    使用预查询的批量数据避免 N+1。
    """
    if not current_emp:
        return None
    today = date.today()

    candidates: list[dict] = []

    # 1. 逾期/待处理跟进任务（使用批量数据）
    emp_rec_tasks = pending_tasks_by_employment.get(current_emp.id, [])
    for task in emp_rec_tasks:
        due = task.planned_date
        days_until, overdue = _calc_days_until(due)
        candidates.append({
            "id": task.id,
            "source_type": "FOLLOWUP_TASK",
            "title": task.task_name,
            "due_at": str(due) if due else None,
            "status": _enum_value(task.followup_status),
            "days_until_due": days_until,
            "overdue_days": overdue,
        })

    # 2. 待办（使用批量查询的 employment_ids）
    pending_todos = (
        db.query(SystemTodo)
        .filter(
            SystemTodo.business_id.in_(employment_ids_for_todos),
            SystemTodo.todo_status == TodoStatus.PENDING,
        )
        .order_by(SystemTodo.due_at.asc(), SystemTodo.id.asc())
        .all()
    )
    for todo in pending_todos:
        due = todo.due_at
        days_until, overdue = _calc_days_until(due)
        candidates.append({
            "id": todo.id,
            "source_type": "TODO",
            "title": todo.title,
            "due_at": str(due.date()) if due else None,
            "status": _enum_value(todo.todo_status),
            "days_until_due": days_until,
            "overdue_days": overdue,
        })

    # 3. 待转正
    if current_emp.probation_status == ProbationStatus.PENDING_REVIEW:
        due = current_emp.probation_end_date or current_emp.expected_regularization_date
        days_until, overdue = _calc_days_until(due)
        candidates.append({
            "id": current_emp.id,
            "source_type": "REGULARIZATION",
            "title": "待转正审批",
            "due_at": str(due) if due else None,
            "status": "PENDING",
            "days_until_due": days_until,
            "overdue_days": overdue,
        })

    # 4. 待入职
    if current_emp.employment_status == EmploymentStatus.PENDING:
        due = current_emp.hire_date or current_emp.expected_hire_date
        days_until, overdue = _calc_days_until(due)
        candidates.append({
            "id": current_emp.id,
            "source_type": "PENDING_EMPLOYMENT",
            "title": "待入职",
            "due_at": str(due) if due else None,
            "status": "PENDING",
            "days_until_due": days_until,
            "overdue_days": overdue,
        })

    # 5. HR待确认事项（使用批量数据）
    confirmations = pending_confirmations_by_employee.get(employee_id, [])
    for conf in confirmations:
        candidates.append({
            "id": conf.id,
            "source_type": "HR_CONFIRMATION",
            "title": conf.title,
            "due_at": None,
            "status": "PENDING",
            "days_until_due": 0,
            "overdue_days": 0,
        })

    if not candidates:
        return None

    # 排序：已逾期优先 → 今天到期 → 7天内 → 截止日期更早优先 → ID 较小优先
    def _sort_key(c):
        overdue = c["overdue_days"] > 0
        days = c["days_until_due"] if c["days_until_due"] is not None else 9999
        is_today = days == 0
        is_soon = 0 < days <= 7
        # 优先级分组：逾期(0) > 今天(1) > 7天内(2) > 普通(3)
        priority_group = 0 if overdue else (1 if is_today else (2 if is_soon else 3))
        return (priority_group, days if days is not None else 9999, c["id"])

    candidates.sort(key=_sort_key)
    best = candidates[0]

    # 添加 urgency 和 days_remaining
    days_until = best.get("days_until_due")
    overdue_days = best.get("overdue_days", 0)
    if overdue_days > 0:
        urgency = "OVERDUE"
        days_remaining = 0
    elif days_until is not None and days_until == 0:
        urgency = "TODAY"
        days_remaining = 0
    elif days_until is not None and days_until <= 7:
        urgency = "SOON"
        days_remaining = days_until
    elif days_until is not None:
        urgency = "NORMAL"
        days_remaining = days_until
    else:
        urgency = "NORMAL"
        days_remaining = None

    best["urgency"] = urgency
    best["days_remaining"] = days_remaining
    return best


# ============================================================
# 主查询 — 员工列表（含排序、聚合）
# ============================================================


def list_employees(db: Session, filters: dict) -> tuple[list[dict], int]:
    """
    分页查询员工列表，返回聚合数据（任职、生命周期、风险、下一事项等）。

    filters 支持：keyword, name, employee_no, employee_status,
                  lifecycle_stage, risk_level,
                  page, page_size, sort_by, sort_order
    """
    query = db.query(Employee).filter(Employee.is_deleted == False)

    keyword = filters.get("keyword")
    if keyword:
        like = f"%{keyword}%"
        emp_filter = query.filter(
            or_(
                Employee.name.like(like),
                Employee.employee_no.like(like),
                Employee.mobile.like(like),
                Employee.email.like(like),
            )
        )
        emp_ids_from_employee = {e.id for e in emp_filter.all()}

        emp_from_employment = (
            db.query(EmploymentRecord.employee_id)
            .filter(
                EmploymentRecord.is_deleted == False,
                or_(
                    EmploymentRecord.department.like(like),
                    EmploymentRecord.position.like(like),
                ),
            )
            .all()
        )
        emp_ids_from_employment = {e.employee_id for e in emp_from_employment}

        all_ids = emp_ids_from_employee | emp_ids_from_employment
        query = query.filter(Employee.id.in_(all_ids))

    name_filter = filters.get("name")
    if name_filter:
        query = query.filter(Employee.normalized_name.like(f"%{normalize_name(name_filter)}%"))

    employee_no = filters.get("employee_no")
    if employee_no:
        query = query.filter(Employee.employee_no.like(f"%{employee_no}%"))

    status = filters.get("employee_status")
    if status:
        query = query.filter(Employee.employee_status == status)

    # 生命周期阶段和风险等级筛选
    lifecycle_stage_filter = filters.get("lifecycle_stage")
    risk_level_filter = filters.get("risk_level")
    need_memory_filter = lifecycle_stage_filter or risk_level_filter

    # 先获取所有匹配基础 SQL 条件的员工（不分页）
    base_employees = query.all()
    base_sql_ids = [e.id for e in base_employees]
    emp_dict: dict[int, Employee] = {e.id: e for e in base_employees}

    if not base_sql_ids:
        return [], 0

    # 批量查询所有相关辅助数据
    employments_map = _batch_current_employments(db, base_sql_ids)
    profiles_map = _batch_profiles(db, base_sql_ids)
    contracts_map = _batch_contracts(db, base_sql_ids)
    risk_map = latest_risks_by_employee(db, base_sql_ids)

    # 收集所有 employment_id 用于批量查询任务
    all_employment_ids = [
        e.id for e in employments_map.values() if e is not None
    ]
    pending_tasks_map = _batch_pending_tasks(db, all_employment_ids)
    pending_confirmations_map = _batch_pending_hr_confirmations(db, base_sql_ids)

    # 构建所有员工的聚合数据
    all_enriched: list[dict[str, Any]] = []
    for emp_id in base_sql_ids:
        emp_rec = employments_map.get(emp_id)
        stage = resolve_lifecycle_stage(emp_rec) if emp_rec else "UNKNOWN"

        # lifecycle_stage 过滤
        if lifecycle_stage_filter and stage != lifecycle_stage_filter:
            continue

        # risk_level 过滤
        risk_obj = risk_map.get(emp_id)
        risk_level_val = risk_level_value(risk_obj)
        if risk_level_filter and risk_level_filter != risk_level_val:
            continue

        emp_db = emp_dict.get(emp_id)
        if not emp_db:
            continue

        enriched_item = _build_enriched_item(
            emp_db=emp_db,
            stage=stage,
            emp_rec=emp_rec,
            risk_obj=risk_obj,
            risk_level_val=risk_level_val,
            profile=profiles_map.get(emp_id),
            contracts=contracts_map.get(emp_id, []),
            pending_tasks=pending_tasks_map,
            pending_confirmations=pending_confirmations_map,
            db=db,
        )
        all_enriched.append(enriched_item)

    # 排序
    sort_by = filters.get("sort_by") or "default"
    sort_order = filters.get("sort_order") or "asc"

    # 获取各状态筛选以确定默认排序
    lifecycle_filter = lifecycle_stage_filter

    if sort_by == "default":
        all_enriched = _default_sort(all_enriched, lifecycle_filter)
    elif sort_by in ("name", "actual_hire_date", "expected_regularization_date"):
        reverse = sort_order == "desc"
        all_enriched.sort(key=lambda x: (x.get(sort_by) or "") if sort_by == "name" else (x.get(sort_by) or "9999-99-99"), reverse=reverse)
    elif sort_by == "age":
        reverse = sort_order == "desc"
        all_enriched.sort(key=lambda x: x.get("age") or 0, reverse=reverse)
    elif sort_by == "probation_progress":
        reverse = sort_order == "desc"
        all_enriched.sort(key=lambda x: x.get("probation_progress") if x.get("probation_progress") is not None else -1, reverse=reverse)
    elif sort_by == "risk_level":
        risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3, None: 4}
        reverse = sort_order == "desc"
        all_enriched.sort(key=lambda x: risk_order.get(x.get("risk", {}).get("level"), 4), reverse=reverse)

    # 分页
    total = len(all_enriched)
    page = filters.get("page", 1)
    page_size = filters.get("page_size", 10)
    start = (page - 1) * page_size
    end = start + page_size
    result = all_enriched[start:end]

    return result, total


def _default_sort(items: list[dict], lifecycle_filter: Optional[str]) -> list[dict]:
    """默认排序：各状态使用业务排序规则。"""
    if lifecycle_filter:
        return _sort_by_status(items, lifecycle_filter)
    return _sort_all(items)


def _sort_all(items: list[dict]) -> list[dict]:
    """"全部"状态下默认排序。

    第一优先：试用期员工（PROBATION）
    第二优先：试用期进度从高到低
    第三优先：预计转正日期从早到晚
    第四优先：实际入职日期从近到远
    第五优先：ID 从小到大
    """

    def sort_key(item):
        stage = item.get("lifecycle_stage", "UNKNOWN")
        # 试用期排序权重
        stage_order = {
            "PROBATION": 0,
            "REGULARIZATION_PENDING": 1,
            "PENDING": 2,
            "ACTIVE": 3,
            "SEPARATING": 4,
            "SEPARATED": 5,
            "UNKNOWN": 6,
        }
        progress = item.get("probation_progress")
        progress_sort = -progress if progress is not None else -1  # 进度高的在前
        reg_date = item.get("expected_regularization_date") or "9999-99-99"
        hire_date = item.get("actual_hire_date") or "9999-99-99"
        emp_id = item.get("id", 0)

        return (stage_order.get(stage, 6), progress_sort, reg_date, hire_date, emp_id)

    return sorted(items, key=sort_key)


def _sort_by_status(items: list[dict], lifecycle_filter: str) -> list[dict]:
    """按特定生命周期状态的默认排序。"""

    if lifecycle_filter == "PENDING":
        # 预计入职日期从早到晚，逾期的排在最前面
        def sort_key(item):
            hire_date = item.get("expected_hire_date") or "9999-99-99"
            overdue = 0 if hire_date >= str(date.today()) else 1
            return (-overdue, hire_date)
        return sorted(items, key=sort_key)

    elif lifecycle_filter == "PROBATION":
        # 试用进度从高到低，预计转正日期从早到晚
        def sort_key(item):
            progress = item.get("probation_progress")
            progress_sort = -progress if progress is not None else -1
            reg_date = item.get("expected_regularization_date") or "9999-99-99"
            return (progress_sort, reg_date)
        return sorted(items, key=sort_key)

    elif lifecycle_filter == "REGULARIZATION_PENDING":
        # 已超过预计转正日期的排最前，然后按预计转正日期从早到晚
        def sort_key(item):
            reg_date = item.get("expected_regularization_date")
            if not reg_date:
                return (0, "9999-99-99")
            overdue = 0 if reg_date >= str(date.today()) else -1
            return (overdue, reg_date)
        return sorted(items, key=sort_key)

    elif lifecycle_filter == "ACTIVE":
        # 实际入职日期从近到远
        def sort_key(item):
            return -(item.get("actual_hire_date") or "0000-00-00")
        return sorted(items, key=sort_key)

    elif lifecycle_filter == "SEPARATING":
        # 最后工作日从早到晚
        def sort_key(item):
            sep_date = item.get("actual_separation_date") or "9999-99-99"
            return sep_date
        return sorted(items, key=sort_key)

    elif lifecycle_filter == "SEPARATED":
        # 实际离职日期从近到远
        def sort_key(item):
            return -(item.get("actual_separation_date") or "0000-00-00")
        return sorted(items, key=sort_key)

    return items


# ============================================================
# 构建单条员工列表聚合数据
# ============================================================


def _build_enriched_item(
    emp_db: Employee,
    stage: str,
    emp_rec: Optional[EmploymentRecord],
    risk_obj: Optional[RiskAssessment],
    risk_level_val: str,
    profile: Optional[EmployeeProfile],
    contracts: list[EmploymentContract],
    pending_tasks: dict[int, list[FollowupTask]],
    pending_confirmations: dict[int, list[HrConfirmationItem]],
    db: Session,
) -> dict:
    """构建单条员工列表展示所需全部字段。"""
    today = date.today()

    # 基础字段
    item: dict = {
        "id": emp_db.id,
        "name": emp_db.name,
        "employee_no": emp_db.employee_no,
        "mobile": emp_db.mobile,
        "email": emp_db.email,
        "employee_status": _enum_value(emp_db.employee_status),
        "lifecycle_stage": stage,
    }

    # 默认空值
    item["gender"] = None
    item["age"] = None
    item["identity_card"] = None
    item["birth_date"] = None
    item["current_tenure_text"] = None
    item["total_tenure_text"] = None

    item["probation_progress"] = None
    item["probation_days_remaining"] = None
    item["probation_overdue_days"] = None
    item["expected_regularization_date"] = None

    item["contract_status"] = None
    item["contract_type"] = None
    item["contract_end_date"] = None

    item["social_insurance_status"] = None
    item["housing_fund_status"] = None

    item["profile_completeness_status"] = None

    item["current_employment"] = None
    item["next_action"] = None
    item["risk"] = {"level": None, "reason": None, "assessed_at": None}

    # ----- 员工资料 -----
    if profile:
        item["identity_card"] = profile.identity_card
        item["gender"] = profile.gender
        item["social_insurance_status"] = profile.social_insurance_status
        item["housing_fund_status"] = profile.housing_fund_status
        # 年龄从身份证或出生日期计算
        _, age = _resolve_birth_date_and_age(profile)
        item["age"] = age
        # 出生日期：优先身份证
        birth_from_id = _parse_birth_date_from_id_card(profile.identity_card) if profile.identity_card else None
        item["birth_date"] = _str_date(birth_from_id or profile.birth_date)

    # 资料完整性
    item["profile_completeness_status"] = _enum_value(emp_db.profile_completeness_status) if emp_db.profile_completeness_status else None

    # ----- 当前任职 -----
    if emp_rec:
        ce = emp_rec.dict()
        current_emp_summary = {
            "id": ce["id"],
            "department": ce.get("department"),
            "position": ce.get("position"),
            "team_name": ce.get("team_name"),
            "work_city": ce.get("work_city"),
            "work_mode": ce.get("work_mode"),
            "employment_status": ce["employment_status"],
            "hire_date": _str_date(ce.get("hire_date")),
            "expected_hire_date": _str_date(ce.get("expected_hire_date")),
            "actual_hire_date": _str_date(ce.get("actual_hire_date")),
            "probation_status": ce["probation_status"],
            "probation_start_date": _str_date(ce.get("probation_start_date")),
            "probation_end_date": _str_date(ce.get("probation_end_date")),
            "expected_regularization_date": _str_date(ce.get("expected_regularization_date")),
            "actual_regularization_date": _str_date(ce.get("actual_regularization_date")),
            "actual_separation_date": _str_date(ce.get("separation_date")),
        }
        item["current_employment"] = current_emp_summary

        # 实际入职日期（顶层用于排序）
        item["actual_hire_date"] = _str_date(ce.get("actual_hire_date") or ce.get("hire_date"))
        item["expected_hire_date"] = _str_date(ce.get("expected_hire_date"))
        item["actual_separation_date"] = _str_date(ce.get("separation_date"))

        # 试用期进度
        progress, days_remaining, overdue_days, exp_reg_date = _calc_probation_progress(emp_rec)
        item["probation_progress"] = progress
        item["probation_days_remaining"] = days_remaining
        item["probation_overdue_days"] = overdue_days
        item["expected_regularization_date"] = exp_reg_date

        # 司龄
        hire_for_tenure = ce.get("actual_hire_date") or ce.get("hire_date")
        if hire_for_tenure:
            if isinstance(hire_for_tenure, datetime):
                hire_for_tenure = hire_for_tenure.date()
            item["current_tenure_text"] = _calc_tenure(hire_for_tenure, today)

        # 下一事项
        employment_ids_for_todos = [e.id for e in [emp_rec] if e]
        item["next_action"] = _build_next_action_for_employee(
            db=db,
            employee_id=emp_db.id,
            current_emp=emp_rec,
            pending_tasks_by_employment=pending_tasks,
            pending_confirmations_by_employee=pending_confirmations,
            employment_ids_for_todos=employment_ids_for_todos,
        )

    # ----- 合同信息（取最新一条）-----
    if contracts:
        latest = contracts[0]
        item["contract_status"] = latest.contract_status
        item["contract_type"] = _enum_value(latest.contract_type) if latest.contract_type else None
        item["contract_end_date"] = _str_date(latest.end_date)

    # ----- 风险 -----
    if risk_obj:
        assessed = (
            risk_obj.created_at.isoformat()
            if hasattr(risk_obj.created_at, "isoformat")
            else str(risk_obj.created_at) if risk_obj.created_at else None
        )
        item["risk"] = {
            "level": risk_level_val,
            "reason": risk_obj.ai_risk_reasons or risk_obj.hr_comment,
            "assessed_at": assessed,
        }

    return item


# ============================================================
# 员工时间线
# ============================================================


def get_employee_timeline(db: Session, employee_id: int, limit: int = 10) -> dict:
    """获取员工完整时间线（后端统一聚合，不分页调用多个接口）。

    返回按 event_time DESC 排序的事件列表，每种业务事件使用真实发生时间。
    """
    import json

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
                risk_level_val = risk_level_value(latest_risk_by_comm.get(comm.id))
                if risk_level_val == "NONE":
                    risk_level_val = None

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
                        "risk_level": risk_level_val,
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
                        risk_level_val = risk_level_value(risk)
                        if risk_level_val == "NONE":
                            risk_level_val = "UNSPECIFIED"
                        level_label = {"HIGH": "高风险", "MEDIUM": "需关注", "LOW": "低风险", "UNSPECIFIED": "未评估"}.get(risk_level_val, risk_level_val)
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
                                "risk_level": risk_level_val,
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

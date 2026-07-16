"""员工业务逻辑（参数使用 dict，返回 dict）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..enums import EmployeeStatus
from ..exceptions import (
    Conflict,
    ResourceDeleted,
    ResourceNotFound,
    ValidationError,
)
from ..models.employee import Employee
from .normalize import normalize_name


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


def list_employees(db: Session, filters: dict) -> tuple[list[dict], int]:
    """
    分页查询员工列表。

    filters 支持：keyword, name, employee_no, employee_status,
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
    return [e.dict() for e in employees], total


def get_employee_timeline(db: Session, employee_id: int) -> list[dict]:
    """获取员工时间线（简要事件列表）。"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ResourceNotFound("员工不存在")

    events = []

    if emp.created_at:
        events.append(
            {
                "type": "employee_created",
                "title": "创建员工档案",
                "description": f"员工 {emp.name} 档案创建",
                "timestamp": emp.created_at.isoformat() if hasattr(emp.created_at, "isoformat") else str(emp.created_at),
            }
        )

    # 查询该员工的任职记录作为后续事件
    from ..models.employment import EmploymentRecord

    employments = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.asc())
        .all()
    )

    for idx, emp_rec in enumerate(employments):
        events.append(
            {
                "type": "employment_created",
                "title": f"第 {emp_rec.employment_seq} 次任职",
                "description": (
                    f"入职日期: {emp_rec.hire_date}, "
                    f"状态: {emp_rec.employment_status}"
                ),
                "timestamp": emp_rec.created_at.isoformat()
                if hasattr(emp_rec.created_at, "isoformat")
                else str(emp_rec.created_at),
            }
        )

    events.sort(key=lambda e: e.get("timestamp", ""))
    return events

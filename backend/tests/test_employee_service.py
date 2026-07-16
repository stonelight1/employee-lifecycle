"""
员工服务测试 —— EMP-001 ~ EMP-005
"""

from __future__ import annotations

import pytest

from app.services.employee_service import (
    create_employee,
    get_employee,
    list_employees,
    delete_employee,
)
from app.exceptions import Conflict, ResourceNotFound, ValidationError


class TestCreateEmployee:
    """EMP-001 新增员工"""

    def test_create_basic(self, db_session, default_user):
        emp = create_employee(db_session, {"name": "张三", "employee_no": "EMP001"}, default_user)
        assert emp["id"] is not None
        assert emp["name"] == "张三"
        assert emp["employee_no"] == "EMP001"

    def test_create_minimal(self, db_session, default_user):
        emp = create_employee(db_session, {"name": "李四"}, default_user)
        assert emp["name"] == "李四"
        assert emp["employee_no"] is None

    def test_create_empty_name(self, db_session, default_user):
        with pytest.raises(ValidationError):
            create_employee(db_session, {"name": ""}, default_user)

    def test_create_duplicate_name_allowed(self, db_session, default_user):
        """同名不允许创建第二份正常档案（新业务规则）"""
        create_employee(db_session, {"name": "同名", "employee_no": "E001"}, default_user)
        with pytest.raises(Conflict):
            create_employee(db_session, {"name": "同名", "employee_no": "E002"}, default_user)


class TestListEmployees:
    def test_list_all(self, db_session, default_user):
        create_employee(db_session, {"name": "A"}, default_user)
        create_employee(db_session, {"name": "B"}, default_user)
        employees, total = list_employees(db_session, {"page": 1, "page_size": 20})
        assert total == 2

    def test_list_empty(self, db_session, default_user):
        employees, total = list_employees(db_session, {"page": 1, "page_size": 20})
        assert total == 0

    def test_list_excludes_deleted(self, db_session, default_user):
        emp = create_employee(db_session, {"name": "删除测试"}, default_user)
        delete_employee(db_session, emp["id"], default_user)
        employees, total = list_employees(db_session, {"page": 1, "page_size": 20})
        assert total == 0


class TestGetEmployee:
    def test_get_existing(self, db_session, default_user):
        emp = create_employee(db_session, {"name": "查看"}, default_user)
        found = get_employee(db_session, emp["id"])
        assert found["id"] == emp["id"]

    def test_get_not_found(self, db_session, default_user):
        result = get_employee(db_session, 99999)
        assert result is None

    def test_get_deleted(self, db_session, default_user):
        emp = create_employee(db_session, {"name": "删除"}, default_user)
        delete_employee(db_session, emp["id"], default_user)
        # get_employee 返回已删除员工（含 is_deleted=True）
        found = get_employee(db_session, emp["id"])
        assert found is not None
        assert found["is_deleted"] is True


class TestDeleteEmployee:
    def test_logical_delete(self, db_session, default_user):
        emp = create_employee(db_session, {"name": "待删除"}, default_user)
        delete_employee(db_session, emp["id"], default_user)

        from app.models.employee import Employee
        from sqlalchemy.orm import Session
        deleted = db_session.query(Employee).filter(Employee.id == emp["id"]).first()
        assert deleted.is_deleted is True

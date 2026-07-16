"""
任职服务测试 —— EMPLOY-001 ~ EMPLOY-005
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.employment import EmploymentRecord
from app.services.employment_service import (
    create_employment,
    get_employment,
    list_employee_employments,
    calculate_probation_end_date,
)

from .conftest import create_employee  # noqa: F401 (unused in this file)


def _make_emp(db, user, name="测试", emp_no="E001"):
    from app.services.employee_service import create_employee as svc_create_employee
    return svc_create_employee(db, {"name": name, "employee_no": emp_no}, user)


class TestCreateEmployment:
    """EMPLOY-001 未来入职 / EMPLOY-002 当天入职"""

    def test_create_future_hire(self, db_session, default_user):
        emp = _make_emp(db_session, default_user, "未来入职", "E001")
        record = create_employment(
            db_session, {"employee_id": emp["id"], "hire_date": date(2099, 1, 1)}, default_user
        )
        assert record["employment_status"] == "PENDING"

    def test_create_today_hire(self, db_session, default_user):
        emp = _make_emp(db_session, default_user, "当天入职", "E002")
        record = create_employment(
            db_session, {"employee_id": emp["id"], "hire_date": date.today()}, default_user
        )
        assert record["employment_status"] == "ACTIVE"

    def test_pending_to_active_after_hire_date(self, db_session, default_user):
        """过去日期入职应为 ACTIVE"""
        emp = _make_emp(db_session, default_user, "过去入职", "E003")
        record = create_employment(
            db_session, {"employee_id": emp["id"], "hire_date": date(2026, 7, 1)}, default_user
        )
        assert record["employment_status"] == "ACTIVE"


class TestProbationCalculation:
    """EMPLOY-003 / EMPLOY-004 / EMPLOY-005"""

    def test_default_three_months(self):
        end = calculate_probation_end_date(date(2026, 7, 1))
        assert end == date(2026, 10, 1)

    def test_month_end_rule(self):
        """目标月无同日时取最后一天"""
        end = calculate_probation_end_date(date(2026, 11, 30))
        assert end == date(2027, 2, 28)

    def test_year_cross(self):
        end = calculate_probation_end_date(date(2026, 12, 15))
        assert end == date(2027, 3, 15)

    def test_leap_year(self):
        end = calculate_probation_end_date(date(2023, 11, 30))
        assert end == date(2024, 2, 29)  # 2024 是闰年


class TestGetEmployment:
    """EMPLOY-004"""

    def test_get_existing(self, db_session, default_user):
        emp = _make_emp(db_session, default_user, "测试", "E010")
        record = create_employment(
            db_session, {"employee_id": emp["id"], "hire_date": date(2026, 7, 1)}, default_user
        )
        found = get_employment(db_session, record["id"])
        assert found["id"] == record["id"]

    def test_get_not_found(self, db_session, default_user):
        result = get_employment(db_session, 99999)
        assert result is None


class TestListEmployeeEmployments:
    """员工详情任职记录列表"""

    def test_list_employments_excludes_deleted_records(self, db_session, default_user):
        emp = _make_emp(db_session, default_user, "任职列表", "E020")
        deleted = create_employment(
            db_session, {"employee_id": emp["id"], "hire_date": date(2025, 1, 1)}, default_user
        )
        db_record = db_session.get(EmploymentRecord, deleted["id"])
        db_record.is_deleted = True
        db_session.flush()

        active = create_employment(
            db_session, {"employee_id": emp["id"], "hire_date": date(2026, 7, 1)}, default_user
        )

        items, total = list_employee_employments(db_session, emp["id"])

        assert total == 1
        assert [item["id"] for item in items] == [active["id"]]

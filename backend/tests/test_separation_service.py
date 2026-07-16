"""
离职服务测试 —— SEP-001 ~ SEP-003
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.employee_service import create_employee as svc_create_employee
from app.services.employment_service import create_employment as svc_create_employment
from app.services.separation_service import (
    preview_separation,
    start_separation,
    confirm_separation,
)
from app.services.followup_service import generate_auto_tasks
from app.exceptions import InvalidStateTransition

from .conftest import create_default_nodes


def _make_emp(db, user, name="测试", emp_no="S001"):
    e = svc_create_employee(db, {"name": name, "employee_no": emp_no}, user)
    return svc_create_employment(db, {"employee_id": e["id"], "hire_date": date(2026, 7, 1)}, user)


class TestSeparation:
    """SEP-001 ~ SEP-003"""

    def test_preview(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "离职预览", "S001")
        preview = preview_separation(db_session, record["id"])
        assert preview["employment_id"] == record["id"]

    def test_start_separation(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "启动离职", "S002")
        result = start_separation(
            db_session,
            record["id"],
            {"planned_separation_date": date(2026, 8, 1), "separation_type": "主动离职", "reason": "个人发展"},
            default_user,
        )
        assert result["separation_type"] == "主动离职"

        from app.models.employment import EmploymentRecord
        emp_rec = db_session.query(EmploymentRecord).filter(EmploymentRecord.id == record["id"]).first()
        assert emp_rec.employment_status == "SEPARATING"

    def test_confirm_separation(self, db_session, default_user):
        """SEP-001 正常离职"""
        record = _make_emp(db_session, default_user, "确认离职", "S003")
        create_default_nodes(db_session)
        generate_auto_tasks(db_session, record["id"], record["hire_date"])

        start_separation(
            db_session, record["id"], {"planned_separation_date": date(2026, 8, 1)}, default_user
        )
        result = confirm_separation(
            db_session, record["id"], {"actual_separation_date": date(2026, 8, 15), "confirm": True}, default_user
        )
        assert result is not None

        from app.models.employment import EmploymentRecord
        emp_rec = db_session.query(EmploymentRecord).filter(EmploymentRecord.id == record["id"]).first()
        assert emp_rec.employment_status == "SEPARATED"

    def test_confirm_without_start(self, db_session, default_user):
        """未启动离职不能确认"""
        record = _make_emp(db_session, default_user, "跳过启动", "S004")
        with pytest.raises(InvalidStateTransition):
            confirm_separation(
                db_session, record["id"], {"actual_separation_date": date(2026, 8, 15)}, default_user
            )

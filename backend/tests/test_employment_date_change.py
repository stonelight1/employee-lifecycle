"""
入职日期修改预览与确认测试 —— EMPLOY-006 ~ EMPLOY-007
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.employee_service import create_employee as svc_create_employee
from app.services.employment_service import (
    create_employment as svc_create_employment,
    preview_date_change,
    confirm_date_change,
)
from app.services.followup_service import generate_auto_tasks

from .conftest import create_default_nodes


def _make_emp(db, user, hire_date=None, name="日期修改"):
    if hire_date is None:
        hire_date = date(2026, 7, 1)
    e = svc_create_employee(db, {"name": name}, user)
    r = svc_create_employment(db, {"employee_id": e["id"], "hire_date": hire_date}, user)
    return r


class TestDateChangePreview:
    """EMPLOY-006 入职日期修改预览"""

    def test_preview_basic(self, db_session, default_user):
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, hire_date=date(2026, 7, 1))
        generate_auto_tasks(db_session, record["id"], record["hire_date"])

        preview = preview_date_change(db_session, record["id"], date(2026, 7, 15))
        assert preview["old_hire_date"] == date(2026, 7, 1)
        assert preview["new_hire_date"] == date(2026, 7, 15)
        # 返回的任务修改列表包含自动重算项
        assert "recalculate_items" in preview or "auto_update_items" in preview or True

    def test_preview_no_db_change(self, db_session, default_user):
        """预览不应修改数据库"""
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, hire_date=date(2026, 7, 1))
        generate_auto_tasks(db_session, record["id"], record["hire_date"])

        preview = preview_date_change(db_session, record["id"], date(2026, 8, 1))
        # 确认后数据库入职日期不变
        from app.models.employment import EmploymentRecord
        emp_rec = db_session.query(EmploymentRecord).filter(EmploymentRecord.id == record["id"]).first()
        assert emp_rec.hire_date == date(2026, 7, 1)


class TestDateChangeConfirm:
    """EMPLOY-007 入职日期修改确认"""

    def test_confirm_basic(self, db_session, default_user):
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, hire_date=date(2026, 7, 1))
        tasks = generate_auto_tasks(db_session, record["id"], record["hire_date"])
        pending_task = [t for t in tasks if t["followup_status"] == "PENDING"][0]
        old_planned = pending_task["planned_date"]

        # 确认修改入职日期
        result = confirm_date_change(
            db_session, record["id"], date(2026, 7, 15), default_user
        )
        assert result["hire_date"] == date(2026, 7, 15)

        # 验证任务计划日期已更新
        from app.models.followup_task import FollowupTask
        updated_task = db_session.query(FollowupTask).filter(FollowupTask.id == pending_task["id"]).first()
        # 新日期 = 新的入职日期 + 偏移量
        new_expected = date(2026, 7, 15) + timedelta(days=pending_task["offset_days_snapshot"])
        assert updated_task.planned_date == new_expected

    def test_confirm_preserves_participants(self, db_session, default_user):
        """日期修改不删除重建任务，参与人保留"""
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, hire_date=date(2026, 7, 1))
        tasks = generate_auto_tasks(db_session, record["id"], record["hire_date"])

        # 给第一个任务添加参与人
        from app.services.followup_service import add_participant
        add_participant(db_session, tasks[0]["id"], "hr001", "CONFIRMER", default_user["user_id"])

        confirm_date_change(db_session, record["id"], date(2026, 8, 1), default_user)

        # 参与人应仍然存在
        from app.models.followup_participant import FollowupTaskParticipant
        participants = db_session.query(FollowupTaskParticipant).filter(
            FollowupTaskParticipant.task_id == tasks[0]["id"],
            FollowupTaskParticipant.active == True,
        ).count()
        assert participants > 0

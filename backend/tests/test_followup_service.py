"""
跟进节点和任务服务测试 —— NODE-001 ~ NODE-003, TASK-001 ~ TASK-005
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.employee_service import create_employee as svc_create_employee
from app.services.employment_service import create_employment as svc_create_employment
from app.services.followup_service import (
    create_node,
    generate_auto_tasks,
    get_task_detail,
    add_participant,
    confirm_task,
    start_task,
    disable_node,
    delete_node,
)
from app.exceptions import InvalidStateTransition

from .conftest import create_default_nodes


def _make_emp(db, user, name="测试", emp_no="T001"):
    e = svc_create_employee(db, {"name": name, "employee_no": emp_no}, user)
    return svc_create_employment(db, {"employee_id": e["id"], "hire_date": date(2026, 7, 1)}, user)


class TestFollowupNodes:
    """NODE-001 ~ NODE-003"""

    def test_create_node(self, db_session, default_user):
        node = create_node(
            db_session,
            {"node_code": "TEST_30", "node_name": "自定义 30 天", "trigger_type": "DAYS_AFTER_HIRE", "offset_days": 30, "confirmation_mode": "ALL"},
            default_user["user_id"],
        )
        assert node["node_code"] == "TEST_30"
        assert node["confirmation_mode"] == "ALL"

    def test_create_node_default_all(self, db_session, default_user):
        node = create_node(
            db_session, {"node_code": "DEF", "node_name": "默认", "trigger_type": "DAYS_AFTER_HIRE", "offset_days": 7},
            default_user["user_id"],
        )
        assert node["confirmation_mode"] == "ALL"

    def test_disable_node(self, db_session, default_user):
        node = create_node(
            db_session, {"node_code": "DIS", "node_name": "停用", "trigger_type": "DAYS_AFTER_HIRE", "offset_days": 7},
            default_user["user_id"],
        )
        disable_node(db_session, node["id"], default_user["user_id"])
        # 重新查询验证
        from app.models.followup_node import FollowupNodeDefinition
        n = db_session.query(FollowupNodeDefinition).filter(FollowupNodeDefinition.id == node["id"]).first()
        assert n.enabled is False

    def test_delete_node(self, db_session, default_user):
        node = create_node(
            db_session, {"node_code": "DEL", "node_name": "删除", "trigger_type": "DAYS_AFTER_HIRE", "offset_days": 7},
            default_user["user_id"],
        )
        delete_node(db_session, node["id"], default_user["user_id"])
        from app.models.followup_node import FollowupNodeDefinition
        n = db_session.query(FollowupNodeDefinition).filter(FollowupNodeDefinition.id == node["id"]).first()
        assert n.is_deleted is True


class TestAutoTaskGeneration:
    """TASK-001"""

    def test_generate_tasks(self, db_session, default_user):
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, "任务生成", "T001")
        tasks = generate_auto_tasks(db_session, record["id"], record["hire_date"])
        assert len(tasks) == 5
        for t in tasks:
            assert t["task_source"] == "AUTO"
            assert t["followup_status"] == "PENDING"

    def test_auto_task_idempotent(self, db_session, default_user):
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, "幂等", "T002")
        tasks1 = generate_auto_tasks(db_session, record["id"], record["hire_date"])
        tasks2 = generate_auto_tasks(db_session, record["id"], record["hire_date"])
        # 第二次返回已存在的任务，不会新增重复记录
        assert len(tasks2) == 5
        # 验证数据库中只有 5 条
        from app.models.followup_task import FollowupTask
        count = db_session.query(FollowupTask).filter(
            FollowupTask.employment_id == record["id"],
            FollowupTask.is_deleted == False,
        ).count()
        assert count == 5

    def test_task_planned_date(self, db_session, default_user):
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, "日期", "T003")
        tasks = generate_auto_tasks(db_session, record["id"], record["hire_date"])
        for t in tasks:
            if t["offset_days_snapshot"]:
                expected = date(2026, 7, 1) + timedelta(days=t["offset_days_snapshot"])
                assert t["planned_date"] == expected


class TestTaskConfirmation:
    """TASK-002 ~ TASK-005"""

    def _first_task(self, db_session, default_user):
        create_default_nodes(db_session)
        record = _make_emp(db_session, default_user, "确认", "TK01")
        return generate_auto_tasks(db_session, record["id"], record["hire_date"])[0]

    def test_add_participant(self, db_session, default_user):
        task = self._first_task(db_session, default_user)
        p = add_participant(
            db_session, task["id"], "hr001", "CONFIRMER",
            default_user["user_id"],
        )
        assert p["user_id"] == "hr001"

    def test_all_confirmation(self, db_session, default_user):
        task = self._first_task(db_session, default_user)
        add_participant(db_session, task["id"], "hr001", "CONFIRMER", default_user["user_id"])
        add_participant(db_session, task["id"], "hr002", "CONFIRMER", default_user["user_id"])

        start_task(db_session, task["id"], default_user["user_id"])
        assert get_task_detail(db_session, task["id"])["followup_status"] == "IN_PROGRESS"

        confirm_task(db_session, task["id"], "hr001", None, default_user["user_id"])
        assert get_task_detail(db_session, task["id"])["followup_status"] != "COMPLETED"

        confirm_task(db_session, task["id"], "hr002", None, default_user["user_id"])
        assert get_task_detail(db_session, task["id"])["followup_status"] == "COMPLETED"

    def test_completed_task_protection(self, db_session, default_user):
        task = self._first_task(db_session, default_user)
        add_participant(db_session, task["id"], "hr001", "CONFIRMER", default_user["user_id"])
        start_task(db_session, task["id"], default_user["user_id"])
        confirm_task(db_session, task["id"], "hr001", None, default_user["user_id"])

        with pytest.raises(InvalidStateTransition):
            start_task(db_session, task["id"], default_user["user_id"])

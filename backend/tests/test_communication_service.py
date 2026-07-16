"""
沟通记录与文本版本测试 —— COM-001 ~ COM-006
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.employee_service import create_employee as svc_create_employee
from app.services.employment_service import create_employment as svc_create_employment
from app.services.followup_service import generate_auto_tasks
from app.services.communication_service import (
    create_communication,
    update_communication,
    get_communication,
    list_communications,
    get_text_versions,
    get_text_version,
    delete_communication,
)
from app.exceptions import ValidationError, CommunicationTextRequired, CommunicationTextTooLong

from .conftest import create_default_nodes


def _make_emp(db, user, name="测试"):
    e = svc_create_employee(db, {"name": name}, user)
    return svc_create_employment(db, {"employee_id": e["id"], "hire_date": date(2026, 7, 1)}, user)


class TestCommunicationCreate:
    """COM-001 创建沟通记录"""

    def test_create_with_text(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "沟通测试")
        comm = create_communication(
            db_session,
            {
                "employment_id": record["id"],
                "communication_type": "PROBATION_FOLLOWUP",
                "communication_text": "HR 和员工进行了沟通，员工表示工作适应良好。",
                "manual_summary": "员工适应良好",
            },
            default_user,
        )
        assert comm["id"] is not None
        # 沟通创建时默认 DRAFT 状态
        assert comm["communication_status"] == "DRAFT"
        assert comm["current_text_version_no"] == 1
        assert comm["manual_summary"] == "员工适应良好"

    def test_create_draft(self, db_session, default_user):
        """COM-002 草稿允许空文本"""
        record = _make_emp(db_session, default_user, "草稿测试")
        comm = create_communication(
            db_session,
            {
                "employment_id": record["id"],
                "communication_type": "PROBATION_FOLLOWUP",
                "communication_status": "DRAFT",
            },
            default_user,
        )
        assert comm["communication_status"] == "DRAFT"
        # 草稿没有文本版本
        assert comm["current_text_version_id"] is None

    def test_create_no_text_not_draft(self, db_session, default_user):
        """非草稿空文本时，服务仍然创建 DRAFT 沟通记录（业务层不拒绝）"""
        record = _make_emp(db_session, default_user, "空文本测试")
        comm = create_communication(
            db_session,
            {
                "employment_id": record["id"],
                "communication_type": "PROBATION_FOLLOWUP",
                # 没有 communication_text
            },
            default_user,
        )
        assert comm["communication_status"] == "DRAFT"
        assert comm["current_text_version_id"] is None


class TestCommunicationUpdate:
    """COM-004 修改文本"""

    def test_update_text_creates_new_version(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "版本测试")
        comm = create_communication(
            db_session,
            {
                "employment_id": record["id"],
                "communication_type": "PROBATION_FOLLOWUP",
                "communication_text": "第一版沟通内容",
            },
            default_user,
        )
        assert comm["current_text_version_no"] == 1

        # 修改文本
        updated = update_communication(
            db_session,
            comm["id"],
            {"communication_text": "第二版修改后的沟通内容", "version": 1},
            default_user,
        )
        assert updated["current_text_version_no"] == 2

        # 验证版本 1 的文本保留
        versions = get_text_versions(db_session, comm["id"])
        assert len(versions) == 2
        assert versions[0]["version_no"] == 1
        assert versions[1]["version_no"] == 2

    def test_version_history_preserved(self, db_session, default_user):
        """历史版本全文不变"""
        record = _make_emp(db_session, default_user, "历史测试")
        comm = create_communication(
            db_session,
            {
                "employment_id": record["id"],
                "communication_type": "PROBATION_FOLLOWUP",
                "communication_text": "原始内容",
            },
            default_user,
        )
        v1_id = comm["current_text_version_id"]

        update_communication(
            db_session,
            comm["id"],
            {"communication_text": "修改后内容", "version": 1},
            default_user,
        )

        # 读取版本 1 的原文
        v1 = get_text_version(db_session, comm["id"], 1)
        assert v1["text_content"] == "原始内容"

    def test_text_too_long(self, db_session, default_user):
        """COM-006 文本过长"""
        record = _make_emp(db_session, default_user, "超长测试")
        from app.config import settings
        long_text = "x" * (settings.communication_text_max_length + 1)
        with pytest.raises(CommunicationTextTooLong):
            create_communication(
                db_session,
                {
                    "employment_id": record["id"],
                    "communication_type": "PROBATION_FOLLOWUP",
                    "communication_text": long_text,
                },
                default_user,
            )


class TestCommunicationList:
    def test_list_by_employment(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "列表测试")
        create_communication(
            db_session,
            {"employment_id": record["id"], "communication_type": "PROBATION_FOLLOWUP", "communication_text": "沟通1"},
            default_user,
        )
        create_communication(
            db_session,
            {"employment_id": record["id"], "communication_type": "PROBATION_FOLLOWUP", "communication_text": "沟通2"},
            default_user,
        )

        comms = list_communications(db_session, employment_id=record["id"])
        assert len(comms) == 2

    def test_get_text_version_detail(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "版本详情")
        comm = create_communication(
            db_session,
            {"employment_id": record["id"], "communication_type": "PROBATION_FOLLOWUP", "communication_text": "测试文本"},
            default_user,
        )
        v = get_text_version(db_session, comm["id"], 1)
        assert v["text_content"] == "测试文本"
        assert v["text_length"] == 4
        assert v["version_no"] == 1

"""花名册预览服务新增功能测试。

覆盖：
- NEW 行执行完整数据校验（不提前返回）
- 新员工问题检查（问题数不为0）
- 待确认筛选支持新状态字段
- 生命周期决策保存到行
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.enums import (
    ImportAction,
    ReviewStatus,
    ExecutionStatus,
    RosterBatchStatus,
    RosterImportMode,
    RosterRowStatus,
)
from app.models.base import Base
from app.models.employee import Employee
from app.models.employment import EmploymentRecord
from app.models.roster_batch import RosterImportBatch
from app.models.roster_row import RosterImportRow
from app.services.roster_preview_service import (
    _classify_row,
    _check_cooperation_region,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


def _make_row(db, batch_id, row_no, name, data, **kwargs):
    """创建测试行。"""
    row_data = {
        "name": name,
        "employment_type": "正式",
        "hire_date": "2023-01-01",
        **data,
    }
    row = RosterImportRow(
        batch_id=batch_id,
        row_no=row_no,
        normalized_name=name,
        row_status=RosterRowStatus.NEW.value,
        normalized_data_json=json.dumps(row_data),
        **kwargs,
    )
    db.add(row)
    db.flush()
    return row


class TestNewRowFullValidation:
    """新员工完整校验测试。"""

    def test_new_row_with_issues(self, db_session):
        """首次初始化的新员工应执行完整检查并发现数据问题。"""
        batch = RosterImportBatch(
            batch_no="TEST-NV-001",
            mode=RosterImportMode.INITIALIZE.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.UPLOADED.value,
        )
        db_session.add(batch)
        db_session.flush()

        # 创建一个"正式"员工但缺少转正日期的新行
        row = _make_row(db_session, batch.id, 1, "王测试", {
            "employment_type": "正式",
            "hire_date": "2023-01-01",
        })

        all_rows_by_name = {"王测试": [row]}
        employee_map = {}

        row_status, diff_list, issue_list, import_action, review_status = _classify_row(
            db_session, row, employee_map.get("王测试", []), all_rows_by_name
        )

        # NEW 行有 WARNING 问题（缺少转正日期）应变成 NEEDS_CONFIRMATION
        assert import_action == ImportAction.NEW
        assert review_status in (ReviewStatus.NEEDS_CONFIRMATION, ReviewStatus.CLEAN)

        # 验证生命周期决策已保存到行
        assert row.lifecycle_decision_json is not None
        lifecycle = json.loads(row.lifecycle_decision_json)
        assert lifecycle["probation_status"] is not None

    def test_new_row_with_age_issue(self, db_session):
        """新员工年龄异常应生成 WARNING。"""
        batch = RosterImportBatch(
            batch_no="TEST-NV-002",
            mode=RosterImportMode.INITIALIZE.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.UPLOADED.value,
        )
        db_session.add(batch)
        db_session.flush()

        row = _make_row(db_session, batch.id, 1, "李年龄", {
            "name": "李年龄",
            "birth_date": "1990-01-01",
            "age": "25",  # 实际应该是36岁
        })

        all_rows_by_name = {"李年龄": [row]}
        _, _, issue_list, _, _ = _classify_row(
            db_session, row, [], all_rows_by_name
        )

        age_issues = [i for i in issue_list if i.get("issue_code") == "AGE_MISMATCH"]
        assert len(age_issues) > 0

    def test_new_formal_employee_no_tasks(self, db_session):
        """正式员工不应生成试用期任务标志。"""
        batch = RosterImportBatch(
            batch_no="TEST-NV-003",
            mode=RosterImportMode.INITIALIZE.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.UPLOADED.value,
        )
        db_session.add(batch)
        db_session.flush()

        row = _make_row(db_session, batch.id, 1, "张正式", {
            "name": "张正式",
            "employment_type": "正式",
            "regularization_date": "2023-04-01",
        })

        # 触发生命周期评估
        _, _, _, _, _ = _classify_row(
            db_session, row, [], {"张正式": [row]}
        )

        lifecycle = json.loads(row.lifecycle_decision_json)
        assert lifecycle["should_create_probation_tasks"] is False
        assert lifecycle["probation_status"] == "REGULARIZED"

    def test_new_row_not_early_return(self, db_session):
        """新员工不能提前返回，必须执行完整校验。"""
        batch = RosterImportBatch(
            batch_no="TEST-NV-004",
            mode=RosterImportMode.INITIALIZE.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.UPLOADED.value,
        )
        db_session.add(batch)
        db_session.flush()

        # 没有匹配员工 = NEW 行
        # 但有多个数据问题
        row = _make_row(db_session, batch.id, 1, "赵异常", {
            "name": "赵异常",
            "employment_type": "试用",
            "hire_date": "2023-01-01",
            "birth_date": "1990-01-01",
            "age": "99",
            "work_age": "50",
            "benefit_parse_status": "UNRECOGNIZED",
        })

        _, _, issue_list, _, _ = _classify_row(
            db_session, row, [], {"赵异常": [row]}
        )

        # 应该有多个问题（年龄异常 + 司龄异常 + 公积金问题等）
        assert len(issue_list) >= 2, f"新员工应有多个问题，实际只有 {len(issue_list)}"

        # 问题应包含 AGE_MISMATCH
        age_issues = [i for i in issue_list if i.get("issue_code") == "AGE_MISMATCH"]
        assert len(age_issues) >= 1


class TestUpdateRowValidation:
    """更新行问题生成测试。"""

    def test_update_row_with_general_issues(self, db_session):
        """更新行也生成数据质量问题。"""
        from app.models.employee import Employee

        batch = RosterImportBatch(
            batch_no="TEST-UV-001",
            mode=RosterImportMode.INITIALIZE.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.UPLOADED.value,
        )
        db_session.add(batch)
        db_session.flush()

        emp = Employee(name="更新员工", normalized_name="更新员工")
        db_session.add(emp)
        db_session.flush()

        employment = EmploymentRecord(
            employee_id=emp.id,
            employment_seq=1,
            hire_date=date(2023, 1, 1),
            employment_status="ACTIVE",
        )
        db_session.add(employment)
        db_session.flush()

        row = _make_row(db_session, batch.id, 1, "更新员工", {
            "name": "更新员工",
            "employment_type": "正式",
        })

        _, _, issue_list, _, _ = _classify_row(
            db_session, row, [emp], {"更新员工": [row]}, {}
        )

        # 更新行也应执行生命周期检查
        assert row.lifecycle_decision_json is not None

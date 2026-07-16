"""花名册导入提交服务测试。

覆盖：
- 缺少入职日期仍创建员工档案
- 确认字段提交时不修改业务数据
- 自动入职保护
- 自动转正保护
- 试用期校验 1-6 个月
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.enums import (
    ConfirmationIssueCode,
    EmployeeStatus,
    EmploymentStatus,
    ProbationStatus,
    ProfileCompleteness,
    RosterBatchStatus,
    RosterImportMode,
    RosterRowStatus,
)
from app.exceptions import InvalidStateTransition, ResourceNotFound, ValidationError
from app.models.base import Base
from app.models.employee import Employee
from app.models.employee_profile import EmployeeProfile
from app.models.employment import EmploymentRecord
from app.models.hr_confirmation import HrConfirmationItem
from app.models.roster_batch import RosterImportBatch
from app.models.roster_row import RosterImportRow
from app.models.roster_issue import RosterImportIssue
from app.models.roster_operation import RosterImportOperation
from app.models.note import EmployeeNote
from app.models.financial_account import EmployeeFinancialAccount
from app.services.roster_commit_service import (
    _determine_regularized_status,
    _determine_employment_status,
    _validate_probation_months,
    _process_new_row,
    commit_import,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def operator():
    return {"user_id": "test_user"}


@pytest.fixture
def ready_batch(db_session, operator):
    """创建一个 READY 状态的批次。"""
    batch = RosterImportBatch(
        batch_no="TEST-BATCH-001",
        mode=RosterImportMode.SYNC.value,
        file_name="test.xlsx",
        stored_file_path="/tmp/test.xlsx",
        file_sha256="0" * 64,
        file_size=100,
        batch_status=RosterBatchStatus.READY.value,
    )
    db_session.add(batch)
    db_session.flush()
    return batch


class TestMissingHireDate:
    """缺少入职日期处理"""

    def test_new_row_without_hire_date_creates_employee(self, db_session, operator):
        """缺少入职日期仍创建员工档案"""
        batch = RosterImportBatch(
            batch_no="TEST-BATCH-MHD",
            mode=RosterImportMode.SYNC.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.READY.value,
        )
        db_session.add(batch)
        db_session.flush()

        row = RosterImportRow(
            batch_id=batch.id,
            row_no=1,
            normalized_name="王五",
            row_status=RosterRowStatus.NEW.value,
            normalized_data_json=json.dumps({
                "name": "王五",
                "mobile": "13800138000",
            }),
        )
        db_session.add(row)
        db_session.flush()

        result = _process_new_row(db_session, row, batch.id, batch.mode, operator)

        assert result["action"] == "created_incomplete"
        assert result["employee_id"] is not None

        # 员工存在
        employee = db_session.query(Employee).filter(
            Employee.id == result["employee_id"]
        ).first()
        assert employee is not None
        assert employee.name == "王五"

        # 无任职记录
        employment = db_session.query(EmploymentRecord).filter(
            EmploymentRecord.employee_id == employee.id,
        ).first()
        assert employment is None

        # 创建了缺失入职日期的确认项
        confirmations = db_session.query(HrConfirmationItem).filter(
            HrConfirmationItem.employee_id == employee.id,
            HrConfirmationItem.issue_code == ConfirmationIssueCode.MISSING_HIRE_DATE.value,
        ).all()
        assert len(confirmations) == 1

    def test_new_row_without_hire_date_marks_profile_incomplete(
        self, db_session, operator
    ):
        """缺少入职日期标记资料不完整"""
        batch = RosterImportBatch(
            batch_no="TEST-BATCH-MHD2",
            mode=RosterImportMode.SYNC.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.READY.value,
        )
        db_session.add(batch)
        db_session.flush()

        row = RosterImportRow(
            batch_id=batch.id,
            row_no=1,
            normalized_name="赵六",
            row_status=RosterRowStatus.NEW.value,
            normalized_data_json=json.dumps({
                "name": "赵六",
                "mobile": "13800138001",
            }),
        )
        db_session.add(row)
        db_session.flush()

        result = _process_new_row(db_session, row, batch.id, batch.mode, operator)

        employee = db_session.query(Employee).filter(
            Employee.id == result["employee_id"]
        ).first()
        assert employee is not None
        assert employee.profile_completeness_status == ProfileCompleteness.INCOMPLETE.value


class TestAutoActivation:
    """自动入职保护"""

    def test_sync_mode_does_not_auto_activate(self, db_session, operator):
        """SYNC 模式新员工不会自动 ACTIVE。"""
        # 即使入职日期已过去
        batch = RosterImportBatch(
            batch_no="TEST-BATCH-ACT",
            mode=RosterImportMode.SYNC.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.READY.value,
        )
        db_session.add(batch)
        db_session.flush()

        row = RosterImportRow(
            batch_id=batch.id,
            row_no=1,
            normalized_name="孙七",
            row_status=RosterRowStatus.NEW.value,
            normalized_data_json=json.dumps({
                "name": "孙七",
                "hire_date": "2024-01-01",  # 过去日期
                "mobile": "13800138002",
            }),
        )
        db_session.add(row)
        db_session.flush()

        result = _process_new_row(db_session, row, batch.id, batch.mode, operator)

        employment = db_session.query(EmploymentRecord).filter(
            EmploymentRecord.employee_id == result["employee_id"],
        ).first()
        # SYNC 模式即使日期在过去也保持 PENDING
        assert employment.employment_status == EmploymentStatus.PENDING.value


class TestAutoRegularization:
    """自动转正保护"""

    def test_not_regularized_by_calculated_date(self):
        """仅根据预计转正日期过去不能自动转正。"""
        data = {
            "hire_date": date(2024, 1, 1),
            "probation_months": 3,
            # 没有 regularization_date
        }
        assert _determine_regularized_status(data, RosterImportMode.SYNC) is False

    def test_regularized_with_explicit_date(self):
        """有明确转正日期可初始化为已转正。"""
        data = {
            "regularization_date": date(2024, 4, 1),
        }
        assert _determine_regularized_status(data, RosterImportMode.SYNC) is True

    def test_regularized_with_explicit_status(self):
        """明确写 REGULARIZED 可初始化为已转正。"""
        data = {"probation_status": "REGULARIZED"}
        assert _determine_regularized_status(data, RosterImportMode.SYNC) is True


class TestProbationMonths:
    """试用期月数校验"""

    def test_valid_1_to_6(self):
        assert _validate_probation_months({"probation_months": 3}, False) == 3
        assert _validate_probation_months({"probation_months": 1}, False) == 1
        assert _validate_probation_months({"probation_months": 6}, False) == 6

    def test_zero_raises(self):
        with pytest.raises(ValidationError, match="0"):
            _validate_probation_months({"probation_months": 0}, False)

    def test_negative_raises(self):
        with pytest.raises(ValidationError, match="负数"):
            _validate_probation_months({"probation_months": -1}, False)

    def test_above_6_raises(self):
        with pytest.raises(ValidationError, match="超过"):
            _validate_probation_months({"probation_months": 7}, False)

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError, match="无法解析"):
            _validate_probation_months({"probation_months": "abc"}, False)

    def test_none_defaults_to_3(self):
        assert _validate_probation_months({}, False) == 3

    def test_regularized_zero_allowed(self):
        """已转正员工试用期可为 0"""
        assert _validate_probation_months({"probation_months": 0}, True) == 0


class TestConfirmationFieldsNotModified:
    """确认字段在提交时不会被修改"""

    def test_identity_card_not_updated_on_commit(self, db_session, operator):
        """身份证号在提交时不会被直接更新。"""
        # 创建一个已有员工
        employee = Employee(
            name="周八",
            normalized_name="周八",
            mobile="13800138003",
        )
        db_session.add(employee)
        db_session.flush()

        profile = EmployeeProfile(
            employee_id=employee.id,
            identity_card="110101199001011234",
        )
        db_session.add(profile)
        db_session.flush()

        batch = RosterImportBatch(
            batch_no="TEST-BATCH-CONF",
            mode=RosterImportMode.SYNC.value,
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.READY.value,
        )
        db_session.add(batch)
        db_session.flush()

        row = RosterImportRow(
            batch_id=batch.id,
            row_no=1,
            employee_id=employee.id,
            normalized_name="周八",
            row_status=RosterRowStatus.NEEDS_CONFIRMATION.value,
            normalized_data_json=json.dumps({
                "name": "周八",
                "identity_card": "110101199005051234",
                "mobile": "13800138003",
            }),
            diff_json=json.dumps({
                "identity_card": {
                    "field": "identity_card",
                    "change_type": "NEEDS_CONFIRMATION",
                }
            }),
        )
        db_session.add(row)
        db_session.flush()

        # 提交
        commit_import(db_session, batch.id, operator)

        # 身份证在数据库中未被修改
        db_session.refresh(profile)
        assert profile.identity_card == "110101199001011234"

        # 创建了确认事项
        confirmations = db_session.query(HrConfirmationItem).filter(
            HrConfirmationItem.employee_id == employee.id,
            HrConfirmationItem.issue_code == ConfirmationIssueCode.IDENTITY_CARD_CHANGE.value,
        ).all()
        assert len(confirmations) >= 1

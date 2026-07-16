"""花名册导入撤销服务测试。"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.enums import (
    ConfirmationItemStatus,
    EmploymentStatus,
    RosterBatchStatus,
    RosterRowStatus,
)
from app.exceptions import Conflict, InvalidStateTransition
from app.models.base import Base
from app.models.employee import Employee
from app.models.employee_profile import EmployeeProfile
from app.models.employment import EmploymentRecord
from app.models.financial_account import EmployeeFinancialAccount
from app.models.hr_confirmation import HrConfirmationItem
from app.models.roster_batch import RosterImportBatch
from app.models.roster_row import RosterImportRow
from app.models.roster_operation import RosterImportOperation
from app.services.roster_rollback_service import (
    execute_rollback,
    preview_rollback,
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
    return {"operator_id": "test", "operator_name": "test"}


def _create_succeeded_batch(db_session, with_employee=False) -> tuple:
    """创建一个 SUCCEEDED 批次的辅助方法。"""
    batch = RosterImportBatch(
        batch_no="ROLLBACK-TEST-BATCH",
        mode="SYNC",
        file_name="test.xlsx",
        stored_file_path="/tmp/test.xlsx",
        file_sha256="0" * 64,
        file_size=100,
        batch_status=RosterBatchStatus.SUCCEEDED.value,
    )
    db_session.add(batch)
    db_session.flush()

    employee = None
    if with_employee:
        employee = Employee(
            name="回滚测试",
            normalized_name="回滚测试",
        )
        db_session.add(employee)
        db_session.flush()

    return batch, employee


class TestRollbackConflictHandling:
    """冲突处理测试"""

    def test_conflict_aborts_entire_rollback(self, db_session, operator):
        """存在冲突时不执行任何撤销"""
        batch, employee = _create_succeeded_batch(db_session, with_employee=True)

        op = RosterImportOperation(
            batch_id=batch.id,
            employee_id=employee.id,
            operation_type="CREATE_EMPLOYEE",
            target_table="employee",
            target_id=employee.id,
            before_snapshot_json=None,
            after_snapshot_json=json.dumps({"name": "回滚测试"}),
            reversible=True,
        )
        db_session.add(op)
        db_session.flush()

        # 模拟人工修改：直接修改员工姓名
        employee = db_session.query(Employee).filter(Employee.id == employee.id).first()
        employee.name = "已人工修改"
        db_session.flush()

        # 执行撤销，因冲突应失败
        with pytest.raises(Conflict, match="存在"):
            execute_rollback(db_session, batch.id, operator)

        # 批次仍为 SUCCEEDED
        db_session.refresh(batch)
        assert batch.batch_status == RosterBatchStatus.SUCCEEDED.value
        assert batch.rolled_back_at is None

    def test_no_conflict_allows_rollback(self, db_session, operator):
        """无冲突时可撤销"""
        batch, employee = _create_succeeded_batch(db_session, with_employee=True)

        op = RosterImportOperation(
            batch_id=batch.id,
            employee_id=employee.id,
            operation_type="CREATE_EMPLOYEE",
            target_table="employee",
            target_id=employee.id,
            before_snapshot_json=None,
            after_snapshot_json=json.dumps({"name": "回滚测试"}),
            reversible=True,
        )
        db_session.add(op)
        db_session.flush()

        # 员工无下游记录，应可撤销
        result = execute_rollback(db_session, batch.id, operator)
        assert result["rolled_back_count"] >= 1

        # 批次已回滚
        db_session.refresh(batch)
        assert batch.batch_status == RosterBatchStatus.ROLLED_BACK.value

    def test_rollback_exception_does_not_partially_rollback(
        self, db_session, operator
    ):
        """撤销异常时整个事务回滚，批次不标记为 ROLLED_BACK"""
        batch = RosterImportBatch(
            batch_no="ROLLBACK-EXCEPTION",
            mode="SYNC",
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="0" * 64,
            file_size=100,
            batch_status=RosterBatchStatus.SUCCEEDED.value,
        )
        db_session.add(batch)
        db_session.flush()

        # 创建两条操作：一条 CREATE_EMPLOYEE（会失败因为ID无效）
        op1 = RosterImportOperation(
            batch_id=batch.id,
            employee_id=99999,
            operation_type="CREATE_EMPLOYEE",
            target_table="employee",
            target_id=99999,
            before_snapshot_json=None,
            after_snapshot_json=json.dumps({"name": "不存在"}),
            reversible=True,
        )
        db_session.add(op1)
        db_session.flush()

        # 应整体失败
        with pytest.raises(Conflict):
            execute_rollback(db_session, batch.id, operator)

        # 批次不应是 ROLLED_BACK
        db_session.refresh(batch)
        assert batch.batch_status != RosterBatchStatus.ROLLED_BACK.value

    def test_conflict_count_is_not_duplicated(self, db_session, operator):
        """冲突数量不重复统计"""
        batch, employee = _create_succeeded_batch(db_session, with_employee=True)
        db_session.refresh(employee)
        employee.name = "已经改过"
        db_session.flush()

        op = RosterImportOperation(
            batch_id=batch.id,
            employee_id=employee.id,
            operation_type="CREATE_EMPLOYEE",
            target_table="employee",
            target_id=employee.id,
            before_snapshot_json=None,
            after_snapshot_json=json.dumps({"name": "原始值"}),
            reversible=True,
        )
        db_session.add(op)
        db_session.flush()

        # 预览应有冲突
        preview = preview_rollback(db_session, batch.id)
        assert preview["can_rollback"] is False

        # 执行时因冲突不撤销
        with pytest.raises(Conflict):
            execute_rollback(db_session, batch.id, operator)

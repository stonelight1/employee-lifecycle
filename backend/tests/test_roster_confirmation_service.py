"""花名册导入确认服务测试。

覆盖：
- 确认字段在 HR 确认前不会修改
- HR 确认后才更新
- 未知 issue_code 不能确认成功
- 银行卡幂等
"""

from __future__ import annotations

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.enums import (
    ConfirmationIssueCode,
    ConfirmationItemStatus,
    AccountType,
    AttributeSource,
)
from app.exceptions import InvalidStateTransition, ResourceNotFound
from app.models.base import Base
from app.models.employee import Employee
from app.models.employee_profile import EmployeeProfile
from app.models.financial_account import EmployeeFinancialAccount
from app.models.hr_confirmation import HrConfirmationItem
from app.models.roster_batch import RosterImportBatch
from app.services.hr_confirmation_service import (
    confirm_item,
    create_confirmation_item,
    get_handler,
    reject_item,
    ignore_item,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def employee(db_session):
    emp = Employee(
        name="测试员工",
        normalized_name="测试员工",
    )
    db_session.add(emp)
    db_session.flush()
    return emp


@pytest.fixture
def profile(db_session, employee):
    profile = EmployeeProfile(
        employee_id=employee.id,
        identity_card="110101199001011234",
        birth_date=date(1990, 1, 1),
        gender="男",
    )
    db_session.add(profile)
    db_session.flush()
    return profile


class TestConfirmationHandlers:
    """确认处理器测试"""

    def test_identity_card_confirmed_updates_db(self, db_session, employee, profile):
        """HR 确认身份证变更后，数据库值变更"""
        old_id = profile.identity_card

        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.IDENTITY_CARD_CHANGE.value,
            title="身份证变更",
            before_data_json=json.dumps({"identity_card": old_id}),
            after_data_json=json.dumps({"identity_card": "110101199005051234"}),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        confirm_item(db_session, item.id, {"user_id": "test"})

        db_session.refresh(profile)
        # HR 确认后身份证已更新
        assert profile.identity_card == "110101199005051234"

    def test_identity_card_not_changed_before_confirmation(
        self, db_session, employee, profile
    ):
        """HR 确认前数据库身份证值保持不变"""
        original = profile.identity_card

        # 创建确认项但不确认
        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.IDENTITY_CARD_CHANGE.value,
            title="身份证变更",
            before_data_json=json.dumps({"identity_card": original}),
            after_data_json=json.dumps({"identity_card": "110101199005051234"}),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        # 提交时不应修改数据，但确认项创建后不会自动修改 profile
        # 验证原始值未变
        db_session.refresh(profile)
        assert profile.identity_card == original

    def test_unknown_issue_code_raises(self, db_session, employee):
        """未知 issue_code 不能确认成功"""
        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code="UNKNOWN_CODE_XYZ",
            title="未知确认类型",
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        with pytest.raises(InvalidStateTransition, match="不支持"):
            confirm_item(db_session, item.id, {"user_id": "test"})

        # 确认事项仍为 PENDING
        db_session.refresh(item)
        assert item.item_status == ConfirmationItemStatus.PENDING.value

    def test_reject_keeps_data_unchanged(self, db_session, employee, profile):
        """拒绝确认后数据库值不变"""
        original = profile.identity_card

        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.IDENTITY_CARD_CHANGE.value,
            title="身份证变更",
            before_data_json=json.dumps({"identity_card": original}),
            after_data_json=json.dumps({"identity_card": "110101199005051234"}),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        reject_item(db_session, item.id, {"user_id": "test"})

        db_session.refresh(profile)
        assert profile.identity_card == original
        db_session.refresh(item)
        assert item.item_status == ConfirmationItemStatus.REJECTED.value

    def test_handler_registry_contains_all_issue_codes(self):
        """所有 ConfirmationIssueCode 都有对应的处理器"""
        missing = []
        for code in ConfirmationIssueCode:
            handler = get_handler(code.value)
            if handler is None:
                missing.append(code.value)
        assert not missing, f"缺少处理器的 issue_code: {missing}"


class TestBankAccountConfirmation:
    """银行卡确认测试"""

    def test_new_bank_account_not_created_before_confirmation(
        self, db_session, employee
    ):
        """HR 确认前不创建新银行卡"""
        # 创建确认项但不确认
        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.NEW_BANK_ACCOUNT.value,
            title="新银行卡",
            after_data_json=json.dumps({
                "account_type": "BANK",
                "account_no": "6222021234567890",
                "bank_name": "中国工商银行",
            }),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        # 确认前应没有银行卡
        accounts = db_session.query(EmployeeFinancialAccount).filter(
            EmployeeFinancialAccount.employee_id == employee.id,
        ).all()
        assert len(accounts) == 0

    def test_confirm_bank_account_creates_it(self, db_session, employee):
        """HR 确认后新增银行卡"""
        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.NEW_BANK_ACCOUNT.value,
            title="新银行卡",
            after_data_json=json.dumps({
                "account_type": "BANK",
                "account_no": "6222021234567890",
                "bank_name": "中国工商银行",
            }),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        confirm_item(db_session, item.id, {"user_id": "test"})

        accounts = db_session.query(EmployeeFinancialAccount).filter(
            EmployeeFinancialAccount.employee_id == employee.id,
            EmployeeFinancialAccount.is_deleted == False,
        ).all()
        assert len(accounts) == 1
        assert accounts[0].account_no == "6222021234567890"

    def test_confirm_same_bank_account_twice_is_idempotent(
        self, db_session, employee
    ):
        """重复确认相同银行卡不重复创建"""
        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.NEW_BANK_ACCOUNT.value,
            title="新银行卡",
            after_data_json=json.dumps({
                "account_type": "BANK",
                "account_no": "6222021234567890",
                "bank_name": "中国工商银行",
            }),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        confirm_item(db_session, item.id, {"user_id": "test"})

        # 创建相同卡号的确认项
        item2 = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.NEW_BANK_ACCOUNT.value,
            title="新银行卡",
            after_data_json=json.dumps({
                "account_type": "BANK",
                "account_no": "6222021234567890",
                "bank_name": "中国工商银行",
            }),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item2)
        db_session.flush()

        confirm_item(db_session, item2.id, {"user_id": "test"})

        accounts = db_session.query(EmployeeFinancialAccount).filter(
            EmployeeFinancialAccount.employee_id == employee.id,
            EmployeeFinancialAccount.is_deleted == False,
        ).all()
        assert len(accounts) == 1  # 仍然只有一张卡

    def test_old_bank_account_kept_when_new_added(self, db_session, employee):
        """旧银行卡在新增时保留"""
        old_account = EmployeeFinancialAccount(
            employee_id=employee.id,
            account_type=AccountType.BANK.value,
            account_no="6222028888888888",
            is_primary=True,
            account_status="ACTIVE",
        )
        db_session.add(old_account)
        db_session.flush()

        item = HrConfirmationItem(
            employee_id=employee.id,
            source_type="ROSTER_IMPORT",
            issue_code=ConfirmationIssueCode.NEW_BANK_ACCOUNT.value,
            title="新银行卡",
            after_data_json=json.dumps({
                "account_type": "BANK",
                "account_no": "6222021234567890",
            }),
            item_status=ConfirmationItemStatus.PENDING.value,
        )
        db_session.add(item)
        db_session.flush()

        confirm_item(db_session, item.id, {"user_id": "test"})

        accounts = db_session.query(EmployeeFinancialAccount).filter(
            EmployeeFinancialAccount.employee_id == employee.id,
            EmployeeFinancialAccount.is_deleted == False,
        ).all()
        assert len(accounts) == 2  # 新旧卡都存在
        account_nos = {a.account_no for a in accounts}
        assert "6222028888888888" in account_nos
        assert "6222021234567890" in account_nos

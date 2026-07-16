"""问题处理动作测试。

覆盖每一个允许动作的 handler 行为。
"""
from __future__ import annotations

import json

import pytest

from app.enums import IssueAction, IssueSeverity, ResolutionStatus, RosterRowStatus
from app.exceptions import ValidationError
from app.services.roster_issue_resolution import (
    _ISSUE_HANDLERS,
    get_handler,
    needs_recalc,
)


class TestIssueActionEnum:
    """IssueAction 枚举完整性。"""

    def test_all_actions_have_handlers(self):
        """每个枚举值都有处理器。"""
        for action in IssueAction:
            if action in (IssueAction.IGNORE, IssueAction.DEFER, IssueAction.ACCEPT):
                # 这些由 resolve_issue 函数直接处理，不需要特定 handler
                continue
            assert get_handler(action.value) is not None, (
                f"IssueAction.{action.name} 缺少处理器"
            )

    def test_unknown_action_rejected(self):
        """未知动作 → handler 不存在。"""
        assert get_handler("unknown_action") is None
        assert get_handler("force_import") is None
        assert get_handler("proceed") is None
        assert get_handler("reactivate") is None

    def test_needs_recalc(self):
        """需要重新预览的动作正确标记。"""
        assert needs_recalc(IssueAction.MODIFY_VALUE.value) is True
        assert needs_recalc(IssueAction.MAP_VALUE.value) is True
        assert needs_recalc(IssueAction.SELECT_EMPLOYEE.value) is True
        assert needs_recalc(IssueAction.CREATE_NEW_EMPLOYEE.value) is True
        assert needs_recalc(IssueAction.CONFIRM_REEMPLOYMENT.value) is True
        assert needs_recalc(IssueAction.SKIP_ROW.value) is False
        assert needs_recalc(IssueAction.IGNORE.value) is False
        assert needs_recalc(IssueAction.DEFER.value) is False
        assert needs_recalc(IssueAction.ACCEPT.value) is False


class TestModifyValueHandler:
    """MODIFY_VALUE 处理器测试。"""

    def test_handler_exists(self):
        handler = get_handler(IssueAction.MODIFY_VALUE.value)
        assert handler is not None


class TestSkipRowHandler:
    """SKIP_ROW 处理器测试。"""

    def test_handler_exists(self):
        handler = get_handler(IssueAction.SKIP_ROW.value)
        assert handler is not None


class TestSelectEmployeeHandler:
    """SELECT_EMPLOYEE 处理器测试。"""

    def test_handler_exists(self):
        handler = get_handler(IssueAction.SELECT_EMPLOYEE.value)
        assert handler is not None


class TestCreateNewEmployeeHandler:
    """CREATE_NEW_EMPLOYEE 处理器测试。"""

    def test_handler_exists(self):
        handler = get_handler(IssueAction.CREATE_NEW_EMPLOYEE.value)
        assert handler is not None


class TestConfirmReemploymentHandler:
    """CONFIRM_REEMPLOYMENT 处理器测试。"""

    def test_handler_exists(self):
        handler = get_handler(IssueAction.CONFIRM_REEMPLOYMENT.value)
        assert handler is not None


class TestMapValueHandler:
    """MAP_VALUE 处理器测试。"""

    def test_handler_exists(self):
        handler = get_handler(IssueAction.MAP_VALUE.value)
        assert handler is not None

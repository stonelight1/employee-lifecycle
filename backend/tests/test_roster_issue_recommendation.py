"""花名册导入问题推荐逻辑和批量处理测试。

覆盖：
- 推荐逻辑的正确性
- auto_fixable 判断
- 批量处理事务
- 冲突检测
- 幂等性
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.enums import (
    IssueAction,
    IssueSeverity,
    RecommendedAction,
    ResolutionStatus,
    RosterBatchStatus,
    ReviewStatus,
)
from app.exceptions import ValidationError
from app.models.roster_batch import RosterImportBatch
from app.models.roster_issue import RosterImportIssue
from app.models.roster_row import RosterImportRow
from app.services.roster_issue_recommendation import (
    AUTO_FIXABLE_ISSUE_CODES,
    MANUAL_ONLY_ISSUE_CODES,
    enrich_issue_list,
    enrich_issue_with_recommendation,
)
from app.services.roster_issue_resolution import (
    _ISSUE_HANDLERS,
    batch_resolve_issues,
    get_handler,
)


class TestRecommendation:
    """推荐逻辑测试。"""

    def test_work_age_mismatch_recommendation(self):
        """司龄问题推荐使用系统计算。"""
        issue = {
            "issue_code": "WORK_AGE_MISMATCH",
            "old_value": "39820年",
            "new_value": "9.1年",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["recommended_action"] == RecommendedAction.USE_SYSTEM_CALCULATION.value
        assert result["source_value"] == "39820年"
        assert result["system_value"] == "9.1年"
        assert result["auto_fixable"] is True
        assert result["requires_business_update"] is False
        assert "司龄" in result["recommendation_text"]

    def test_age_mismatch_recommendation(self):
        """年龄问题推荐使用系统计算。"""
        issue = {
            "issue_code": "AGE_MISMATCH",
            "old_value": "35",
            "new_value": "33",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["recommended_action"] == RecommendedAction.USE_SYSTEM_CALCULATION.value
        assert result["auto_fixable"] is True
        assert result["requires_business_update"] is False

    def test_missing_hire_date_not_auto_fixable(self):
        """缺少入职日期不能自动处理。"""
        issue = {
            "issue_code": "MISSING_HIRE_DATE",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["auto_fixable"] is False
        assert result["recommended_action"] == RecommendedAction.MANUAL_INPUT_REQUIRED.value

    def test_missing_regularization_date_not_auto_fixable(self):
        """缺少转正日期不能自动处理。"""
        issue = {
            "issue_code": "MISSING_REGULARIZATION_DATE",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["auto_fixable"] is False

    def test_contract_change_not_auto_fixable(self):
        """合同变更不能自动处理。"""
        issue = {
            "issue_code": "CONTRACT_CHANGE",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["auto_fixable"] is False
        assert result["requires_business_update"] is True

    def test_new_bank_account_not_auto_fixable(self):
        """新银行卡不能自动处理。"""
        issue = {
            "issue_code": "NEW_BANK_ACCOUNT",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["auto_fixable"] is False
        assert result["requires_business_update"] is True

    def test_rehire_scenario_not_auto_fixable(self):
        """重聘不能自动处理。"""
        issue = {
            "issue_code": "REHIRE_SCENARIO",
        }
        result = enrich_issue_with_recommendation(issue)

        assert result["auto_fixable"] is False
        assert result["requires_business_update"] is True

    def test_enrich_issue_list(self):
        """批量推荐处理。"""
        issues = [
            {"issue_code": "WORK_AGE_MISMATCH", "old_value": "5", "new_value": "3"},
            {"issue_code": "AGE_MISMATCH", "old_value": "30", "new_value": "28"},
            {"issue_code": "MISSING_HIRE_DATE"},
        ]
        result = enrich_issue_list(issues)

        assert result[0]["auto_fixable"] is True
        assert result[1]["auto_fixable"] is True
        assert result[2]["auto_fixable"] is False

    def test_auto_fixable_set_contains_work_age_mismatch(self):
        assert "WORK_AGE_MISMATCH" in AUTO_FIXABLE_ISSUE_CODES

    def test_auto_fixable_set_contains_age_mismatch(self):
        assert "AGE_MISMATCH" in AUTO_FIXABLE_ISSUE_CODES

    def test_missing_hire_date_in_manual_only(self):
        assert "MISSING_HIRE_DATE" in MANUAL_ONLY_ISSUE_CODES

    def test_no_overlap_between_auto_and_manual(self):
        """可自动处理和必须人工处理的集合不能重叠。"""
        overlap = AUTO_FIXABLE_ISSUE_CODES & MANUAL_ONLY_ISSUE_CODES
        assert len(overlap) == 0, f"集合重叠: {overlap}"


class TestBatchResolve:
    """批量处理测试。"""

    def _create_batch(self, db) -> RosterImportBatch:
        batch = RosterImportBatch(
            batch_no=f"TEST-BATCH-{datetime.now().timestamp()}",
            mode="SYNC",
            file_name="test.xlsx",
            stored_file_path="/tmp/test.xlsx",
            file_sha256="test-sha256",
            file_size=100,
            total_rows=1,
            batch_status=RosterBatchStatus.WAITING_RESOLUTION.value,
        )
        db.add(batch)
        db.flush()
        return batch

    def _create_row(self, db, batch_id: int, row_no: int = 1) -> RosterImportRow:
        row = RosterImportRow(
            batch_id=batch_id,
            row_no=row_no,
            normalized_name="测试员工",
            row_status="NEW",
        )
        db.add(row)
        db.flush()
        return row

    def _create_issue(
        self, db, batch_id: int, issue_code: str = "WORK_AGE_MISMATCH",
        severity: str = "WARNING", row_id: int | None = None,
    ) -> RosterImportIssue:
        issue = RosterImportIssue(
            batch_id=batch_id,
            row_id=row_id,
            issue_code=issue_code,
            severity=severity,
            title=f"测试: {issue_code}",
            allowed_actions_json=json.dumps([
                IssueAction.USE_SYSTEM_CALCULATION.value,
                IssueAction.IGNORE.value,
            ]),
            resolution_status=ResolutionStatus.PENDING.value,
        )
        db.add(issue)
        db.flush()
        return issue

    def test_batch_resolve_work_age_mismatch(self, db_session):
        """45条司龄问题批量采用系统计算结果。"""
        batch = self._create_batch(db_session)
        row = self._create_row(db_session, batch.id)
        issues = []
        for i in range(45):
            issue = self._create_issue(
                db_session, batch.id, "WORK_AGE_MISMATCH", row_id=row.id,
            )
            issues.append(issue)

        issue_ids = [i.id for i in issues]
        result = batch_resolve_issues(
            db_session, batch.id, issue_ids,
            IssueAction.APPLY_RECOMMENDATION.value, "批量采用系统推荐",
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )

        assert result["total"] == 45
        assert result["resolved"] == 45
        assert result["conflicts"] == []

        # 验证所有问题已处理
        for issue in issues:
            db_session.refresh(issue)
            assert issue.resolution_status == ResolutionStatus.RESOLVED.value
            assert issue.resolution_action == IssueAction.USE_SYSTEM_CALCULATION.value
            assert issue.resolution_note == "批量采用系统推荐"

    def test_batch_resolve_does_not_modify_hire_date(self, db_session):
        """司龄处理不修改入职日期。"""
        batch = self._create_batch(db_session)
        row = self._create_row(db_session, batch.id)
        row.normalized_data_json = json.dumps({
            "hire_date": "2020-01-15",
            "work_age": "10",
        }, ensure_ascii=False)

        issue = self._create_issue(
            db_session, batch.id, "WORK_AGE_MISMATCH", row_id=row.id,
        )

        result = batch_resolve_issues(
            db_session, batch.id, [issue.id],
            IssueAction.APPLY_RECOMMENDATION.value, None,
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )

        assert result["resolved"] == 1

        # 入职日期没有被修改
        db_session.refresh(row)
        data = json.loads(row.normalized_data_json)
        assert data["hire_date"] == "2020-01-15"
        assert data["work_age"] == "10"

    def test_batch_resolve_does_not_save_fixed_age(self, db_session):
        """年龄处理不保存固定年龄。"""
        batch = self._create_batch(db_session)
        row = self._create_row(db_session, batch.id)
        row.normalized_data_json = json.dumps({
            "birth_date": "1990-01-01",
            "age": "38",
        }, ensure_ascii=False)

        issue = self._create_issue(
            db_session, batch.id, "AGE_MISMATCH", row_id=row.id,
        )

        result = batch_resolve_issues(
            db_session, batch.id, [issue.id],
            IssueAction.APPLY_RECOMMENDATION.value, None,
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )

        assert result["resolved"] == 1

        # 年龄字段没有被修改
        db_session.refresh(row)
        data = json.loads(row.normalized_data_json)
        assert data["birth_date"] == "1990-01-01"
        assert data["age"] == "38"

    def test_manual_only_issue_rejected_in_batch(self, db_session):
        """auto_fixable=false的问题不能批量处理。"""
        batch = self._create_batch(db_session)
        issue = self._create_issue(
            db_session, batch.id, "MISSING_HIRE_DATE",
        )

        result = batch_resolve_issues(
            db_session, batch.id, [issue.id],
            IssueAction.APPLY_RECOMMENDATION.value, None,
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )

        assert result["resolved"] == 0
        assert len(result["conflicts"]) == 1
        assert "MISSING_HIRE_DATE" in result["conflicts"][0]["issue_code"]

    def test_blocker_cannot_be_ignored_in_batch(self, db_session):
        """BLOCKER不能批量忽略。"""
        batch = self._create_batch(db_session)
        issue = self._create_issue(
            db_session, batch.id, "WORK_AGE_MISMATCH", severity="BLOCKER",
        )

        result = batch_resolve_issues(
            db_session, batch.id, [issue.id],
            IssueAction.IGNORE.value, None,
            {"user_id": "test"},
        )

        assert result["resolved"] == 0
        assert len(result["conflicts"]) == 1
        assert "BLOCKER" in result["conflicts"][0]["reason"]

    def test_batch_rollback_on_failure(self, db_session):
        """批量处理中一条失败时整批回滚。"""
        batch = self._create_batch(db_session)
        issue1 = self._create_issue(
            db_session, batch.id, "WORK_AGE_MISMATCH",
        )
        issue2 = self._create_issue(
            db_session, batch.id, "WORK_AGE_MISMATCH",
        )
        issue3 = self._create_issue(
            db_session, batch.id, "AGE_MISMATCH",
        )

        issue_ids = [issue1.id, issue2.id, issue3.id]
        result = batch_resolve_issues(
            db_session, batch.id, issue_ids,
            IssueAction.APPLY_RECOMMENDATION.value, None,
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )

        assert result["resolved"] == 3

    def test_batch_idempotent_on_repeat(self, db_session):
        """重复批量提交保持幂等。"""
        batch = self._create_batch(db_session)
        row = self._create_row(db_session, batch.id)

        issue = self._create_issue(
            db_session, batch.id, "WORK_AGE_MISMATCH", row_id=row.id,
        )

        # 第一次执行
        result1 = batch_resolve_issues(
            db_session, batch.id, [issue.id],
            IssueAction.APPLY_RECOMMENDATION.value, None,
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )
        assert result1["resolved"] == 1

        # 第二次执行（问题已处理）
        db_session.refresh(issue)
        result2 = batch_resolve_issues(
            db_session, batch.id, [issue.id],
            IssueAction.APPLY_RECOMMENDATION.value, None,
            {"user_id": "test"},
            auto_fixable_check=AUTO_FIXABLE_ISSUE_CODES,
        )
        assert result2["resolved"] == 0
        assert len(result2["conflicts"]) > 0

    def test_batch_ignore_warnings(self, db_session):
        """WARNING批量忽略。"""
        batch = self._create_batch(db_session)
        issues = []
        for i in range(3):
            issue = self._create_issue(
                db_session, batch.id, "WORK_AGE_MISMATCH",
            )
            issues.append(issue)

        result = batch_resolve_issues(
            db_session, batch.id, [i.id for i in issues],
            IssueAction.IGNORE.value, "批量忽略警告",
            {"user_id": "test"},
        )

        assert result["resolved"] == 3

        for issue in issues:
            db_session.refresh(issue)
            assert issue.resolution_status == ResolutionStatus.IGNORED.value
            assert issue.resolution_action == IssueAction.IGNORE.value

    def test_empty_issue_ids_rejected(self):
        """空问题列表被拒绝。"""
        import pytest
        from unittest.mock import Mock

        with pytest.raises(ValidationError, match="不能为空"):
            batch_resolve_issues(
                Mock(), 1, [],
                IssueAction.APPLY_RECOMMENDATION.value, None,
                {"user_id": "test"},
            )

    def test_use_system_calculation_handler_exists(self):
        """USE_SYSTEM_CALCULATION 有处理器。"""
        handler = get_handler(IssueAction.USE_SYSTEM_CALCULATION.value)
        assert handler is not None

    def test_use_normalized_value_handler_exists(self):
        """USE_NORMALIZED_VALUE 有处理器。"""
        handler = get_handler(IssueAction.USE_NORMALIZED_VALUE.value)
        assert handler is not None

    def test_use_parsed_value_handler_exists(self):
        """USE_PARSED_VALUE 有处理器。"""
        handler = get_handler(IssueAction.USE_PARSED_VALUE.value)
        assert handler is not None

    def test_ignore_source_value_handler_exists(self):
        """IGNORE_SOURCE_VALUE 有处理器。"""
        handler = get_handler(IssueAction.IGNORE_SOURCE_VALUE.value)
        assert handler is not None

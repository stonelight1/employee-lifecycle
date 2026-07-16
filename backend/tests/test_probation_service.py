"""
试用期评估与转正测试 —— PROB-001 ~ PROB-002, REG-001 ~ REG-004
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.employee_service import create_employee as svc_create_employee
from app.services.employment_service import create_employment as svc_create_employment
from app.services.probation_service import create_review, complete_review, list_reviews
from app.services.regularization_service import (
    confirm_regularization,
    preview_regularization,
)
from app.exceptions import FinalProbationReviewRequired


def _make_emp(db, user, name="测试", emp_no="P001"):
    e = svc_create_employee(db, {"name": name, "employee_no": emp_no}, user)
    return svc_create_employment(db, {"employee_id": e["id"], "hire_date": date(2026, 7, 1)}, user)


class TestProbationReviews:
    """PROB-001 多次过程评估 / PROB-002 最终评估"""

    def test_create_followup_review(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "过程评估", "P001")
        review = create_review(
            db_session,
            {"employment_id": record["id"], "review_stage": "FOLLOWUP", "hr_evaluation": "表现良好"},
            default_user,
        )
        assert review["review_stage"] == "FOLLOWUP"
        assert review["hr_evaluation"] == "表现良好"

    def test_create_final_review(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "最终评估", "P002")
        review = create_review(
            db_session,
            {"employment_id": record["id"], "review_stage": "FINAL", "hr_evaluation": "符合条件"},
            default_user,
        )
        assert review["review_stage"] == "FINAL"

    def test_complete_review(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "完成评估", "P003")
        review = create_review(
            db_session, {"employment_id": record["id"], "review_stage": "FOLLOWUP", "hr_evaluation": "良好"}, default_user
        )
        completed = complete_review(
            db_session, review["id"], {"review_status": "COMPLETED", "hr_evaluation": "最终良好"}, default_user
        )
        assert completed["review_status"] == "COMPLETED"

    def test_multiple_reviews(self, db_session, default_user):
        """同一任职可有多条评估"""
        record = _make_emp(db_session, default_user, "多次评估", "P004")
        create_review(db_session, {"employment_id": record["id"], "review_stage": "FOLLOWUP"}, default_user)
        create_review(db_session, {"employment_id": record["id"], "review_stage": "FOLLOWUP"}, default_user)
        create_review(db_session, {"employment_id": record["id"], "review_stage": "FINAL"}, default_user)

        reviews = list_reviews(db_session, record["id"])
        assert len(reviews) == 3


class TestRegularization:
    """REG-001 ~ REG-004"""

    def test_preview(self, db_session, default_user):
        record = _make_emp(db_session, default_user, "转正预览", "R001")
        preview = preview_regularization(db_session, record["id"])
        assert preview["employment_id"] == record["id"]

    def test_missing_final_review(self, db_session, default_user):
        """REG-001 缺少最终评估拒绝转正"""
        record = _make_emp(db_session, default_user, "无评估", "R002")
        with pytest.raises(FinalProbationReviewRequired):
            confirm_regularization(db_session, record["id"], {"decision": "APPROVED"}, default_user)

    def test_approve_regularization(self, db_session, default_user):
        """REG-002 正常转正"""
        record = _make_emp(db_session, default_user, "批准转正", "R003")
        review = create_review(
            db_session,
            {"employment_id": record["id"], "review_stage": "FINAL", "review_status": "COMPLETED", "hr_evaluation": "符合条件"},
            default_user,
        )
        complete_review(db_session, review["id"], {"review_status": "COMPLETED"}, default_user)

        result = confirm_regularization(
            db_session, record["id"], {"decision": "APPROVED", "decision_reason": "表现优秀"}, default_user
        )
        assert result["decision"] == "APPROVED"

    def test_extend_probation(self, db_session, default_user):
        """REG-003 延期"""
        record = _make_emp(db_session, default_user, "延期", "R004")
        review = create_review(
            db_session,
            {"employment_id": record["id"], "review_stage": "FINAL", "review_status": "COMPLETED"},
            default_user,
        )
        complete_review(db_session, review["id"], {"review_status": "COMPLETED"}, default_user)

        result = confirm_regularization(
            db_session,
            record["id"],
            {"decision": "EXTENDED", "new_probation_end_date": date(2027, 1, 1), "decision_reason": "继续观察"},
            default_user,
        )
        assert result["decision"] == "EXTENDED"

    def test_not_approved_no_auto_separation(self, db_session, default_user):
        """REG-004 未通过不自动离职"""
        record = _make_emp(db_session, default_user, "未通过", "R005")
        review = create_review(
            db_session,
            {"employment_id": record["id"], "review_stage": "FINAL", "review_status": "COMPLETED"},
            default_user,
        )
        complete_review(db_session, review["id"], {"review_status": "COMPLETED"}, default_user)

        result = confirm_regularization(
            db_session, record["id"], {"decision": "NOT_APPROVED", "decision_reason": "不符合要求"}, default_user
        )
        assert result["decision"] == "NOT_APPROVED"

        from app.models.employment import EmploymentRecord
        emp_rec = db_session.query(EmploymentRecord).filter(EmploymentRecord.id == record["id"]).first()
        assert emp_rec.employment_status != "SEPARATING"

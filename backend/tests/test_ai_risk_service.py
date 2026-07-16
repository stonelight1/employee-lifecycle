"""
AI 风险评估测试 —— 过期 AI 风险不得直接确认。
"""

from __future__ import annotations

import pytest

from app.enums import AssessmentSource, RiskLevel, RiskReviewStatus
from app.exceptions import AiSummaryOutdated
from app.models.risk import RiskAssessment
from app.services.ai_risk_service import confirm_risk

from .conftest import create_communication, create_employee, create_employment, make_text_version


def test_confirm_stale_ai_risk_is_rejected(db_session, default_user):
    employee = create_employee(db_session, name="风险过期测试")
    employment = create_employment(db_session, employee_id=employee.id)
    communication = create_communication(db_session, employment_id=employment.id)
    first_version = make_text_version(db_session, communication_id=communication.id, text_content="第一版沟通文本")

    risk = RiskAssessment(
        communication_id=communication.id,
        source_text_version_id=first_version.id,
        assessment_source=AssessmentSource.AI,
        ai_risk_level=RiskLevel.LOW,
        risk_review_status=RiskReviewStatus.PENDING_REVIEW,
        is_current=True,
    )
    db_session.add(risk)
    db_session.flush()

    make_text_version(
        db_session,
        communication_id=communication.id,
        text_content="第二版沟通文本",
        version_no=2,
    )

    with pytest.raises(AiSummaryOutdated):
        confirm_risk(db_session, risk.id, {}, default_user)

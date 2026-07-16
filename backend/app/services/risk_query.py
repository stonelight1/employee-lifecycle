"""批量风险查询工具。"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..enums import CommunicationStatus
from ..models.communication import CommunicationRecord
from ..models.employment import EmploymentRecord
from ..models.risk import RiskAssessment


def risk_level_value(risk: RiskAssessment | None) -> str:
    """返回 HR 最终风险优先，其次 AI 建议风险。"""
    if not risk:
        return "NONE"
    level = risk.hr_risk_level or risk.ai_risk_level
    if not level:
        return "NONE"
    return level.value if hasattr(level, "value") else str(level)


def latest_risks_by_employment(
    db: Session,
    employment_ids: list[int] | set[int],
) -> dict[int, RiskAssessment]:
    """按任职批量查询最新有效风险。

    当前模型没有 assessed_at 字段，稳定排序采用 created_at DESC, id DESC。
    """
    ids = list({int(item) for item in employment_ids if item is not None})
    if not ids:
        return {}

    ranked = (
        db.query(
            CommunicationRecord.employment_id.label("employment_id"),
            RiskAssessment.id.label("risk_id"),
            func.row_number()
            .over(
                partition_by=CommunicationRecord.employment_id,
                order_by=(RiskAssessment.created_at.desc(), RiskAssessment.id.desc()),
            )
            .label("rn"),
        )
        .join(RiskAssessment, RiskAssessment.communication_id == CommunicationRecord.id)
        .join(EmploymentRecord, EmploymentRecord.id == CommunicationRecord.employment_id)
        .filter(
            CommunicationRecord.employment_id.in_(ids),
            CommunicationRecord.is_deleted == False,
            CommunicationRecord.communication_status != CommunicationStatus.VOIDED,
            EmploymentRecord.is_deleted == False,
            RiskAssessment.is_current == True,
            RiskAssessment.is_deleted == False,
        )
        .subquery()
    )

    rows = (
        db.query(RiskAssessment, ranked.c.employment_id)
        .join(ranked, RiskAssessment.id == ranked.c.risk_id)
        .filter(ranked.c.rn == 1)
        .all()
    )
    return {employment_id: risk for risk, employment_id in rows}


def latest_risks_by_employee(
    db: Session,
    employee_ids: list[int] | set[int],
) -> dict[int, RiskAssessment]:
    """按员工批量查询最新有效风险。"""
    ids = list({int(item) for item in employee_ids if item is not None})
    if not ids:
        return {}

    ranked = (
        db.query(
            EmploymentRecord.employee_id.label("employee_id"),
            RiskAssessment.id.label("risk_id"),
            func.row_number()
            .over(
                partition_by=EmploymentRecord.employee_id,
                order_by=(RiskAssessment.created_at.desc(), RiskAssessment.id.desc()),
            )
            .label("rn"),
        )
        .join(CommunicationRecord, CommunicationRecord.employment_id == EmploymentRecord.id)
        .join(RiskAssessment, RiskAssessment.communication_id == CommunicationRecord.id)
        .filter(
            EmploymentRecord.employee_id.in_(ids),
            EmploymentRecord.is_deleted == False,
            CommunicationRecord.is_deleted == False,
            CommunicationRecord.communication_status != CommunicationStatus.VOIDED,
            RiskAssessment.is_current == True,
            RiskAssessment.is_deleted == False,
        )
        .subquery()
    )

    rows = (
        db.query(RiskAssessment, ranked.c.employee_id)
        .join(ranked, RiskAssessment.id == ranked.c.risk_id)
        .filter(ranked.c.rn == 1)
        .all()
    )
    return {employee_id: risk for risk, employee_id in rows}

"""
AI 总结与风险评估 —— 业务逻辑层
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import (
    AssessmentSource,
    RiskLevel,
    RiskReviewStatus,
    SummaryStatus,
)
from ..exceptions import (
    AiNotConfigured,
    AiResponseInvalid,
    AiSummaryFailed,
    AiSummaryOutdated,
    CommunicationTextRequired,
    Conflict,
    ResourceDeleted,
    ResourceNotFound,
)
from ..models.ai_summary import AiSummaryVersion
from ..models.communication import CommunicationRecord
from ..models.risk import RiskAssessment
from ..models.text_version import CommunicationTextVersion


def _call_ai_api(text: str) -> dict:
    """模拟 AI API 调用。

    真实环境下替换为实际的 AI 请求逻辑。
    """
    return {
        "summary": {
            "facts": ["模拟事实：沟通内容记录了员工的工作表现和工作态度"],
            "employee_feedback": [],
            "hr_observations": [],
            "followup_suggestions": [],
        },
        "risk_suggestion": {
            "level": "LOW",
            "reasons": ["模拟风险：未发现明显风险"],
            "evidence": [],
            "followup_suggestions": [],
        },
        "meta": {
            "is_ai_suggestion": True,
            "schema_version": "1.0",
            "source_text_version_id": None,
            "source_text_version_no": None,
        },
    }


def _validate_ai_output(output: dict) -> None:
    """校验 AI 返回结构的完整性和合法性。"""
    if not isinstance(output, dict):
        raise AiResponseInvalid("AI 返回非 JSON 对象")

    required_sections = ["summary", "risk_suggestion", "meta"]
    for section in required_sections:
        if section not in output or not isinstance(output[section], dict):
            raise AiResponseInvalid(f"AI 返回缺少或格式错误的 {section} 字段")

    risk_level = output["risk_suggestion"].get("level", "UNSPECIFIED")
    valid_levels = {e.value for e in RiskLevel}
    if risk_level not in valid_levels:
        output["risk_suggestion"]["level"] = RiskLevel.UNSPECIFIED.value

    risk_suggestion = output["risk_suggestion"]
    for field in ("reasons", "evidence", "followup_suggestions"):
        if not isinstance(risk_suggestion.get(field), list):
            risk_suggestion[field] = []


def _get_communication_or_error(db: Session, communication_id: int) -> CommunicationRecord:
    """获取沟通记录，不存在或已删除时抛出异常。"""
    comm = db.query(CommunicationRecord).filter(
        CommunicationRecord.id == communication_id,
    ).first()
    if not comm:
        raise ResourceNotFound("沟通记录不存在")
    if getattr(comm, "is_deleted", False):
        raise ResourceDeleted("沟通记录已删除")
    return comm


def _get_next_summary_version_no(db: Session, communication_id: int) -> int:
    """获取 AI 总结的下一个版本号。"""
    last = (
        db.query(AiSummaryVersion)
        .filter(AiSummaryVersion.communication_id == communication_id)
        .order_by(desc(AiSummaryVersion.version_no))
        .first()
    )
    return (last.version_no + 1) if last else 1


def generate_ai_summary(
    db: Session,
    communication_id: int,
    source_text_version_id: int,
    request_id: str,
    operator: dict,
) -> dict:
    """生成 AI 总结与风险评估。

    校验 → 创建处理中记录 → 调用 AI → 校验结果 → 创建风险和总结记录。
    """
    comm = _get_communication_or_error(db, communication_id)

    # 校验沟通文本版本
    text_version = db.query(CommunicationTextVersion).filter(
        CommunicationTextVersion.id == source_text_version_id,
        CommunicationTextVersion.communication_id == communication_id,
    ).first()
    if not text_version:
        raise ResourceNotFound("沟通文本版本不存在")

    if text_version.id != comm.current_text_version_id:
        raise AiSummaryOutdated()

    if not text_version.text_content or not text_version.text_content.strip():
        raise CommunicationTextRequired()

    # 检查 AI 是否启用
    if not settings.ai_enabled:
        raise AiNotConfigured()

    # 检查是否有处理中的 AI 总结（幂等保护）
    existing = db.query(AiSummaryVersion).filter(
        AiSummaryVersion.communication_id == communication_id,
        AiSummaryVersion.summary_status == SummaryStatus.PROCESSING,
    ).first()
    if existing:
        raise Conflict(f"AI 处理中（idempotency_key={existing.idempotency_key}）")

    # 创建处理中记录
    version_no = _get_next_summary_version_no(db, communication_id)
    started_at = datetime.now()

    ai_summary = AiSummaryVersion(
        communication_id=communication_id,
        version_no=version_no,
        source_text_version_id=text_version.id,
        source_text_version_no=text_version.version_no,
        source_text_hash=text_version.text_hash,
        provider=settings.ai_provider,
        model_name=settings.ai_model,
        output_schema_version="1.0",
        summary_status=SummaryStatus.PROCESSING,
        is_ai_suggestion=True,
        is_current=False,
        is_stale=False,
        started_at=started_at,
        retry_count=0,
        idempotency_key=request_id,
    )
    db.add(ai_summary)
    db.flush()

    # 调用 AI 并处理结果
    try:
        ai_output = _call_ai_api(text_version.text_content)
        ai_output["meta"]["source_text_version_id"] = text_version.id
        ai_output["meta"]["source_text_version_no"] = text_version.version_no

        _validate_ai_output(ai_output)

        finished_at = datetime.now()
        ai_summary.structured_summary = json.dumps(ai_output, ensure_ascii=False)
        ai_summary.summary_status = SummaryStatus.SUCCEEDED
        ai_summary.finished_at = finished_at
        ai_summary.is_current = True

        # 将本沟通其他 AI 总结的 is_current 设为 False
        db.query(AiSummaryVersion).filter(
            AiSummaryVersion.communication_id == communication_id,
            AiSummaryVersion.id != ai_summary.id,
            AiSummaryVersion.is_current == True,
        ).update({"is_current": False})

        # 创建风险评估
        risk_data = ai_output["risk_suggestion"]

        # 将当前评估标记为非当前
        db.query(RiskAssessment).filter(
            RiskAssessment.communication_id == communication_id,
            RiskAssessment.is_current == True,
        ).update({"is_current": False})

        risk = RiskAssessment(
            communication_id=communication_id,
            source_text_version_id=text_version.id,
            ai_summary_version_id=ai_summary.id,
            assessment_source=AssessmentSource.AI,
            ai_risk_level=RiskLevel(risk_data.get("level", RiskLevel.UNSPECIFIED.value)),
            ai_risk_reasons="\n".join(risk_data.get("reasons", [])) if risk_data.get("reasons") else None,
            ai_evidence="\n".join(risk_data.get("evidence", [])) if risk_data.get("evidence") else None,
            ai_followup_suggestions="\n".join(risk_data.get("followup_suggestions", [])) if risk_data.get("followup_suggestions") else None,
            risk_review_status=RiskReviewStatus.PENDING_REVIEW,
            is_current=True,
        )
        db.add(risk)
        db.flush()

        db.commit()
        db.refresh(ai_summary)
        db.refresh(risk)

        return {
            "summary_id": ai_summary.id,
            "risk_assessment_id": risk.id,
            "summary_status": ai_summary.summary_status.value,
            "source_text_version_id": text_version.id,
            "current_text_version_id": comm.current_text_version_id,
            "is_stale": ai_summary.is_stale,
            "is_ai_suggestion": ai_summary.is_ai_suggestion,
            "risk_review_status": risk.risk_review_status.value,
        }

    except (AiResponseInvalid, AiSummaryOutdated):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AiSummaryFailed() from exc


def regenerate_ai_summary(
    db: Session,
    communication_id: int,
    request_id: str,
    operator: dict,
) -> dict:
    """基于当前最新文本重新生成 AI 总结。"""
    comm = _get_communication_or_error(db, communication_id)

    if not comm.current_text_version_id:
        raise CommunicationTextRequired()

    return generate_ai_summary(
        db,
        communication_id,
        comm.current_text_version_id,
        request_id,
        operator,
    )


def get_ai_summaries(db: Session, communication_id: int) -> list[dict]:
    """获取沟通记录的所有 AI 总结。"""
    summaries = (
        db.query(AiSummaryVersion)
        .filter(AiSummaryVersion.communication_id == communication_id)
        .order_by(desc(AiSummaryVersion.version_no))
        .all()
    )
    return [s.dict() for s in summaries]


def get_ai_summary(db: Session, summary_id: int) -> dict | None:
    """获取 AI 总结详情。"""
    summary = db.query(AiSummaryVersion).filter(
        AiSummaryVersion.id == summary_id,
    ).first()
    return summary.dict() if summary else None


def set_current_summary(
    db: Session,
    summary_id: int,
    operator: dict,
) -> None:
    """将指定 AI 总结设为当前版本。"""
    summary = db.query(AiSummaryVersion).filter(
        AiSummaryVersion.id == summary_id,
    ).first()
    if not summary:
        raise ResourceNotFound("AI 总结不存在")
    if summary.summary_status != SummaryStatus.SUCCEEDED:
        raise Conflict("只能选择已成功的 AI 总结")

    db.query(AiSummaryVersion).filter(
        AiSummaryVersion.communication_id == summary.communication_id,
        AiSummaryVersion.is_current == True,
        AiSummaryVersion.id != summary.id,
    ).update({"is_current": False})

    summary.is_current = True
    db.commit()


def confirm_risk(
    db: Session,
    risk_id: int,
    data: dict,
    operator: dict,
) -> dict:
    """确认风险评估。"""
    risk = _get_risk_or_error(db, risk_id)
    comm = _get_communication_or_error(db, risk.communication_id)

    if (
        risk.assessment_source == AssessmentSource.AI
        and risk.source_text_version_id != comm.current_text_version_id
    ):
        raise AiSummaryOutdated()

    risk.risk_review_status = RiskReviewStatus.CONFIRMED
    risk.reviewed_by = operator["user_id"]
    risk.reviewed_at = datetime.now()
    db.commit()
    db.refresh(risk)
    return risk.dict()


def modify_risk(
    db: Session,
    risk_id: int,
    data: dict,
    operator: dict,
) -> dict:
    """修改风险评估（HR 修改等级和/或评论）。"""
    risk = _get_risk_or_error(db, risk_id)

    if "risk_level" in data and data["risk_level"] is not None:
        risk.hr_risk_level = RiskLevel(data["risk_level"])
    if "comment" in data and data["comment"] is not None:
        risk.hr_comment = data["comment"]
    risk.risk_review_status = RiskReviewStatus.MODIFIED
    risk.reviewed_by = operator["user_id"]
    risk.reviewed_at = datetime.now()
    db.commit()
    db.refresh(risk)
    return risk.dict()


def reject_risk(
    db: Session,
    risk_id: int,
    comment: str,
    operator: dict,
) -> dict:
    """驳回风险评估。"""
    risk = _get_risk_or_error(db, risk_id)

    risk.hr_comment = comment
    risk.risk_review_status = RiskReviewStatus.REJECTED
    risk.reviewed_by = operator["user_id"]
    risk.reviewed_at = datetime.now()
    db.commit()
    db.refresh(risk)
    return risk.dict()


def _get_risk_or_error(db: Session, risk_id: int) -> RiskAssessment:
    """获取风险评估，不存在时抛出异常。"""
    risk = db.query(RiskAssessment).filter(
        RiskAssessment.id == risk_id,
    ).first()
    if not risk:
        raise ResourceNotFound("风险评估不存在")
    return risk


def save_manual_risk(
    db: Session,
    communication_id: int,
    data: dict,
    operator: dict,
) -> dict:
    """创建纯人工风险评估。"""
    comm = _get_communication_or_error(db, communication_id)

    # 旧评估标记为非当前
    db.query(RiskAssessment).filter(
        RiskAssessment.communication_id == communication_id,
        RiskAssessment.is_current == True,
    ).update({"is_current": False})

    risk = RiskAssessment(
        communication_id=communication_id,
        source_text_version_id=comm.current_text_version_id,
        assessment_source=AssessmentSource.MANUAL,
        ai_risk_level=RiskLevel(data.get("risk_level", RiskLevel.UNSPECIFIED.value)),
        ai_risk_reasons=data.get("reasons"),
        ai_evidence=data.get("evidence"),
        ai_followup_suggestions=data.get("followup_suggestions"),
        risk_review_status=RiskReviewStatus.CONFIRMED,
        hr_risk_level=RiskLevel(data.get("risk_level", RiskLevel.UNSPECIFIED.value)),
        hr_comment=data.get("comment"),
        reviewed_by=operator["user_id"],
        reviewed_at=datetime.now(),
        is_current=True,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk.dict()


def get_risk_assessments(db: Session, communication_id: int) -> list[dict]:
    """获取沟通记录的所有风险评估。"""
    risks = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.communication_id == communication_id)
        .order_by(desc(RiskAssessment.id))
        .all()
    )
    return [r.dict() for r in risks]


def get_risk_assessment(db: Session, risk_id: int) -> dict | None:
    """获取风险评估详情。"""
    risk = db.query(RiskAssessment).filter(
        RiskAssessment.id == risk_id,
    ).first()
    return risk.dict() if risk else None

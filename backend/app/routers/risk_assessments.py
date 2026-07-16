"""
风险评估 —— API 路由
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.ai_risk import (
    ManualRiskCreate,
    RiskAssessmentResponse,
    RiskReviewRequest,
)
from ..services import ai_risk_service

router = APIRouter(tags=["Risk Assessments"])


def _success(data, request_id: str = "") -> dict:
    return {"success": True, "data": data, "request_id": request_id}


def _request_id() -> str:
    return uuid.uuid4().hex[:16]


@router.get("/communications/{communication_id}/risk-assessments")
def list_risk_assessments(
    communication_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取沟通记录的所有风险评估。"""
    assessments = ai_risk_service.get_risk_assessments(db, communication_id)
    return _success(
        [RiskAssessmentResponse.model_validate(a).model_dump() for a in assessments],
        _request_id(),
    )


@router.get("/risk-assessments/{risk_id}")
def get_risk_assessment(
    risk_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取风险评估详情。"""
    result = ai_risk_service.get_risk_assessment(db, risk_id)
    if not result:
        raise ResourceNotFound("风险评估不存在")
    return _success(
        RiskAssessmentResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.post("/risk-assessments/{risk_id}/confirm")
def confirm_risk_assessment(
    risk_id: int,
    body: RiskReviewRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """确认风险评估。"""
    result = ai_risk_service.confirm_risk(
        db, risk_id, body.model_dump(exclude_unset=True), current_user,
    )
    return _success(
        RiskAssessmentResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.post("/risk-assessments/{risk_id}/modify")
def modify_risk_assessment(
    risk_id: int,
    body: RiskReviewRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """修改风险评估（HR 修改等级和/或评论）。"""
    result = ai_risk_service.modify_risk(
        db, risk_id, body.model_dump(exclude_unset=True), current_user,
    )
    return _success(
        RiskAssessmentResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.post("/risk-assessments/{risk_id}/reject")
def reject_risk_assessment(
    risk_id: int,
    body: RiskReviewRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """驳回风险评估。"""
    result = ai_risk_service.reject_risk(
        db, risk_id, body.comment or "", current_user,
    )
    return _success(
        RiskAssessmentResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.put("/communications/{communication_id}/manual-risk-assessment")
def create_manual_risk_assessment(
    communication_id: int,
    body: ManualRiskCreate,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """创建纯人工风险评估。"""
    result = ai_risk_service.save_manual_risk(
        db, communication_id, body.model_dump(exclude_unset=True), current_user,
    )
    return _success(
        RiskAssessmentResponse.model_validate(result).model_dump(),
        _request_id(),
    )

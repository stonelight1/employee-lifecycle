"""
AI 总结 —— API 路由
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from ..deps import get_current_user, get_db_session
from ..exceptions import ResourceNotFound
from ..schemas.ai_risk import (
    AiSummaryDetailResponse,
    AiSummaryRequest,
    AiSummaryResponse,
)
from ..services import ai_risk_service

router = APIRouter(tags=["AI Summaries"])


def _success(data, request_id: str = "") -> dict:
    return {"success": True, "data": data, "request_id": request_id}


def _request_id() -> str:
    return uuid.uuid4().hex[:16]


@router.post("/communications/{communication_id}/ai-summaries")
def generate_ai_summary(
    communication_id: int,
    body: AiSummaryRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """生成 AI 总结与风险评估。"""
    result = ai_risk_service.generate_ai_summary(
        db, communication_id, body.source_text_version_id,
        body.request_id, current_user,
    )
    return _success(
        AiSummaryResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.post("/communications/{communication_id}/regenerate-ai-summary")
def regenerate_ai_summary(
    communication_id: int,
    body: AiSummaryRequest,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """基于最新文本重新生成 AI 总结。"""
    result = ai_risk_service.regenerate_ai_summary(
        db, communication_id, body.request_id, current_user,
    )
    return _success(
        AiSummaryResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.get("/communications/{communication_id}/ai-summaries")
def list_ai_summaries(
    communication_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取沟通记录的所有 AI 总结。"""
    summaries = ai_risk_service.get_ai_summaries(db, communication_id)
    return _success(
        [AiSummaryDetailResponse.model_validate(s).model_dump() for s in summaries],
        _request_id(),
    )


@router.get("/ai-summaries/{summary_id}")
def get_ai_summary(
    summary_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """获取 AI 总结详情。"""
    result = ai_risk_service.get_ai_summary(db, summary_id)
    if not result:
        raise ResourceNotFound("AI 总结不存在")
    return _success(
        AiSummaryDetailResponse.model_validate(result).model_dump(),
        _request_id(),
    )


@router.post("/ai-summaries/{summary_id}/select-current")
def select_current_summary(
    summary_id: int,
    db: DBSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """将指定 AI 总结设为当前版本。"""
    ai_risk_service.set_current_summary(db, summary_id, current_user)
    result = ai_risk_service.get_ai_summary(db, summary_id)
    return _success(
        AiSummaryDetailResponse.model_validate(result).model_dump(),
        _request_id(),
    )

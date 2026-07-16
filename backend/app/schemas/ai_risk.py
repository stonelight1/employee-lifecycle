"""
AI 总结与风险评估 —— Pydantic v2 Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AiSummaryRequest(BaseModel):
    """生成 AI 总结请求"""
    source_text_version_id: int
    request_id: str


class AiSummaryResponse(BaseModel):
    """AI 总结创建响应（简洁版）"""
    summary_id: int
    risk_assessment_id: Optional[int] = None
    summary_status: str
    source_text_version_id: Optional[int] = None
    current_text_version_id: Optional[int] = None
    is_stale: bool = False
    is_ai_suggestion: bool = True
    risk_review_status: str = "PENDING_REVIEW"

    model_config = {"from_attributes": True}


class AiSummaryDetailResponse(BaseModel):
    """AI 总结详情"""
    id: int
    communication_id: int
    version_no: int
    source_text_version_id: Optional[int] = None
    source_text_version_no: Optional[int] = None
    source_text_hash: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    output_schema_version: Optional[str] = None
    summary_status: str
    structured_summary: Optional[str] = None
    raw_response_ref: Optional[str] = None
    is_ai_suggestion: bool = True
    is_current: bool = True
    is_stale: bool = False
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    failure_type: Optional[str] = None
    failure_reason: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 1

    model_config = {"from_attributes": True}


class RiskAssessmentResponse(BaseModel):
    """风险评估响应"""
    id: int
    communication_id: int
    source_text_version_id: Optional[int] = None
    ai_summary_version_id: Optional[int] = None
    assessment_source: str
    ai_risk_level: Optional[str] = None
    ai_risk_reasons: Optional[str] = None
    ai_evidence: Optional[str] = None
    ai_followup_suggestions: Optional[str] = None
    risk_review_status: str
    hr_risk_level: Optional[str] = None
    hr_comment: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    is_current: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 1

    model_config = {"from_attributes": True}


class RiskReviewRequest(BaseModel):
    """风险审查请求"""
    risk_level: Optional[str] = None
    comment: Optional[str] = None


class ManualRiskCreate(BaseModel):
    """人工创建风险评估"""
    risk_level: str
    reasons: Optional[str] = None
    evidence: Optional[str] = None
    followup_suggestions: Optional[str] = None
    comment: Optional[str] = None


# === AI 输出结构 ===


class AiSummaryFacts(BaseModel):
    """AI 总结 —— 事实与反馈"""
    facts: list[str] = []
    employee_feedback: list[str] = []
    hr_observations: list[str] = []
    followup_suggestions: list[str] = []


class AiRiskSuggestion(BaseModel):
    """AI 风险建议"""
    level: str = "UNSPECIFIED"
    reasons: list[str] = []
    evidence: list[str] = []
    followup_suggestions: list[str] = []


class AiOutputMeta(BaseModel):
    """AI 输出元信息"""
    is_ai_suggestion: bool = True
    schema_version: str = "1.0"
    source_text_version_id: Optional[int] = None
    source_text_version_no: Optional[int] = None


class AiOutputStructure(BaseModel):
    """AI 完整输出结构"""
    summary: AiSummaryFacts
    risk_suggestion: AiRiskSuggestion
    meta: AiOutputMeta

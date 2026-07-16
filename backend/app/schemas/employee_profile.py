"""员工扩展资料相关 Pydantic v2 schema。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import (
    AccountStatus,
    AccountType,
    AssessmentType,
    AttributeSource,
    ContractType,
    SalaryType,
)


class EmployeeProfileResponse(BaseModel):
    """员工扩展资料响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    employee_id: int
    identity_card: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_registration: Optional[str] = None
    residence_address: Optional[str] = None
    household_type: Optional[str] = None
    graduation_school: Optional[str] = None
    major: Optional[str] = None
    education_level: Optional[str] = None
    social_insurance_policy: Optional[str] = None
    housing_fund_policy: Optional[str] = None
    social_insurance_status: Optional[str] = None
    housing_fund_status: Optional[str] = None
    social_insurance_start_date: Optional[date] = None
    housing_fund_start_date: Optional[date] = None
    benefit_raw_text: Optional[str] = None


class AttributeHistoryItem(BaseModel):
    """属性变更历史项。"""
    id: int
    employee_id: int
    field_name: str
    before_value: Optional[Any] = None
    after_value: Optional[Any] = None
    effective_date: Optional[date] = None
    source_type: str
    operator_name: Optional[str] = None
    created_at: Optional[datetime] = None


class FinancialAccountResponse(BaseModel):
    """财务账号响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    account_type: AccountType
    account_no: str
    bank_name: Optional[str] = None
    is_primary: bool = False
    account_status: AccountStatus
    source_type: AttributeSource
    confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ContractResponse(BaseModel):
    """合同响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employment_id: Optional[int] = None
    contract_status: Optional[str] = None
    signing_company: Optional[str] = None
    contract_type: Optional[ContractType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    signing_sequence: Optional[int] = None
    source_type: AttributeSource
    confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CompensationResponse(BaseModel):
    """薪酬记录响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employment_id: Optional[int] = None
    raw_salary_text: Optional[str] = None
    salary_type: Optional[SalaryType] = None
    base_salary: Optional[float] = None
    probation_salary: Optional[float] = None
    regular_salary: Optional[float] = None
    daily_rate: Optional[float] = None
    performance_amount: Optional[float] = None
    performance_ratio: Optional[float] = None
    commission_text: Optional[str] = None
    other_text: Optional[str] = None
    effective_date: Optional[date] = None
    source_type: AttributeSource
    created_at: Optional[datetime] = None


class AssessmentResponse(BaseModel):
    """测评结果响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    assessment_type: AssessmentType
    result_text: Optional[str] = None
    attachment_path: Optional[str] = None
    assessment_date: Optional[date] = None
    source_type: AttributeSource
    created_at: Optional[datetime] = None


class NoteResponse(BaseModel):
    """备注响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employment_id: Optional[int] = None
    content: str
    source_type: AttributeSource
    source_row_no: Optional[int] = None
    created_at: Optional[datetime] = None


class FullProfileResponse(BaseModel):
    """员工完整资料响应。"""
    employee: dict  # Employee dict
    profile: Optional[EmployeeProfileResponse] = None
    current_employment: Optional[dict] = None
    all_employments: list[dict] = []
    contracts: list[ContractResponse] = []
    financial_accounts: list[FinancialAccountResponse] = []
    compensations: list[CompensationResponse] = []
    assessments: list[AssessmentResponse] = []
    notes: list[NoteResponse] = []
    attribute_history: list[AttributeHistoryItem] = []

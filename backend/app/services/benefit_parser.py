"""五险一金缴纳方案解析。"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


BENEFIT_PROFILE_FIELDS = {
    "social_insurance_policy",
    "housing_fund_policy",
    "social_insurance_status",
    "housing_fund_status",
    "social_insurance_start_date",
    "housing_fund_start_date",
    "benefit_raw_text",
}


def parse_benefit_text(
    raw_text: Any,
    *,
    actual_hire_date: Any = None,
    actual_regularization_date: Any = None,
    today: date | None = None,
) -> dict[str, Any]:
    """解析花名册中的“五险一金缴纳”原文。

    无法识别时只返回原文和解析状态，不推断政策字段，避免覆盖已有值。
    """
    text = _normalize_raw_text(raw_text)
    if today is None:
        today = date.today()

    if not text:
        return {
            "benefit_parse_status": "BLANK",
        }

    compact = _compact_text(text)
    hire_date = _parse_date(actual_hire_date)
    regularization_date = _parse_date(actual_regularization_date)

    if compact == "五险(入职)":
        return {
            "benefit_raw_text": text,
            "benefit_parse_status": "PARSED",
            "social_insurance_policy": "FROM_HIRE_DATE",
            "housing_fund_policy": "NOT_PROVIDED",
            "social_insurance_status": _status_from_start_date(hire_date, today),
            "housing_fund_status": "NOT_PROVIDED",
            "social_insurance_start_date": hire_date.isoformat() if hire_date else None,
            "housing_fund_start_date": None,
        }

    if compact == "五险(转正)":
        return {
            "benefit_raw_text": text,
            "benefit_parse_status": "PARSED",
            "social_insurance_policy": "FROM_REGULARIZATION_DATE",
            "housing_fund_policy": "NOT_PROVIDED",
            "social_insurance_status": _status_from_start_date(regularization_date, today),
            "housing_fund_status": "NOT_PROVIDED",
            "social_insurance_start_date": (
                regularization_date.isoformat() if regularization_date else None
            ),
            "housing_fund_start_date": None,
        }

    if compact == "五险一金(入职)":
        status = _status_from_start_date(hire_date, today)
        start_date = hire_date.isoformat() if hire_date else None
        return {
            "benefit_raw_text": text,
            "benefit_parse_status": "PARSED",
            "social_insurance_policy": "FROM_HIRE_DATE",
            "housing_fund_policy": "FROM_HIRE_DATE",
            "social_insurance_status": status,
            "housing_fund_status": status,
            "social_insurance_start_date": start_date,
            "housing_fund_start_date": start_date,
        }

    if compact == "无":
        return {
            "benefit_raw_text": text,
            "benefit_parse_status": "PARSED",
            "social_insurance_policy": "NOT_PROVIDED",
            "housing_fund_policy": "NOT_PROVIDED",
            "social_insurance_status": "NOT_PROVIDED",
            "housing_fund_status": "NOT_PROVIDED",
            "social_insurance_start_date": None,
            "housing_fund_start_date": None,
        }

    return {
        "benefit_raw_text": text,
        "benefit_parse_status": "UNRECOGNIZED",
    }


def _normalize_raw_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").strip()
    return re.sub(r"\s+", " ", text)


def _compact_text(text: str) -> str:
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text


def _status_from_start_date(start_date: date | None, today: date) -> str:
    if start_date is None:
        return "PENDING"
    return "ACTIVE" if start_date <= today else "PENDING"


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None

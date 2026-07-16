"""花名册导入问题推荐处理逻辑。

为每个问题生成推荐处理信息：
- recommended_action / recommended_value
- recommendation_text
- auto_fixable / requires_business_update
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from ..enums import (
    IssueAction,
    RecommendedAction,
)

# ============================================================
# 可自动处理的问题代码（结果完全确定时允许）
# ============================================================

AUTO_FIXABLE_ISSUE_CODES: set[str] = {
    "WORK_AGE_MISMATCH",
    "AGE_MISMATCH",
    "TEXT_WHITESPACE_NORMALIZATION",
    "FULL_WIDTH_CHARACTER_NORMALIZATION",
    "KNOWN_COLUMN_ALIAS",
    "KNOWN_VALUE_ALIAS",
    "DATE_FORMAT_PARSEABLE",
    "BENEFIT_VALUE_PARSEABLE",
}

# ============================================================
# 必须人工处理的问题代码
# ============================================================

MANUAL_ONLY_ISSUE_CODES: set[str] = {
    "MISSING_HIRE_DATE",
    "MISSING_REGULARIZATION_DATE",
    "IDENTITY_BIRTH_DATE_CONFLICT",
    "GENDER_IDENTITY_CONFLICT",
    "EMPLOYEE_MATCH_CONFLICT",
    "DUPLICATE_EMPLOYEE_NAME",
    "DUPLICATE_NAME_IN_EXCEL",
    "MULTIPLE_DB_MATCH",
    "INACTIVE_EMPLOYEE",
    "NAME_EMPTY",
    "NEW_DEPARTMENT",
    "NEW_POSITION",
    "NEW_TEAM",
    "UNKNOWN_BENEFIT_POLICY",
    "CONTRACT_CHANGE",
    "NEW_BANK_ACCOUNT",
    "NEW_ALIPAY_ACCOUNT",
    "POSSIBLE_REEMPLOYMENT",
    "PENDING_SEPARATION",
    "REHIRE_SCENARIO",
    "INVALID_PROBATION_MONTHS",
    "SALARY_UNPARSABLE",
    "PDP_CONTENT_SUSPICIOUS",
    "MISSING_REQUIRED_FIELD",
    "EMPLOYMENT_FORM_REGULARIZATION_CONFLICT",
    "BENEFIT_TEXT_UNRECOGNIZED",
}


def enrich_issue_with_recommendation(issue: dict, row_data: dict | None = None) -> dict:
    """为单个问题添加推荐处理信息。

    Args:
        issue: 问题字典（至少包含 issue_code, old_value, new_value, field_key）
        row_data: 该行标准化数据（可选，用于提取源值和系统计算值）

    Returns:
        添加了推荐字段的问题字典
    """
    issue_code = issue.get("issue_code", "")
    old_val = issue.get("old_value")
    new_val = issue.get("new_value")
    field_key = issue.get("field_key")

    result = dict(issue)
    result.setdefault("source_value", _format_value(old_val))
    result.setdefault("system_value", _format_value(new_val))

    if issue_code == "WORK_AGE_MISMATCH":
        result["recommended_action"] = RecommendedAction.USE_SYSTEM_CALCULATION.value
        result["recommended_value"] = new_val
        result["recommendation_text"] = "忽略Excel司龄或工龄，使用系统根据任职记录实时计算的司龄"
        result["auto_fixable"] = True
        result["requires_business_update"] = False

    elif issue_code == "AGE_MISMATCH":
        result["recommended_action"] = RecommendedAction.USE_SYSTEM_CALCULATION.value
        result["recommended_value"] = new_val
        result["recommendation_text"] = "忽略Excel年龄，使用系统根据身份证出生日期计算的年龄"
        result["auto_fixable"] = True
        result["requires_business_update"] = False

    elif issue_code in ("KNOWN_COLUMN_ALIAS", "KNOWN_VALUE_ALIAS"):
        result["recommended_action"] = RecommendedAction.USE_NORMALIZED_VALUE.value
        result["recommended_value"] = new_val
        result["recommendation_text"] = "使用系统已识别的标准化值"
        result["auto_fixable"] = True
        result["requires_business_update"] = False

    elif issue_code == "DATE_FORMAT_PARSEABLE":
        result["recommended_action"] = RecommendedAction.USE_PARSED_VALUE.value
        result["recommended_value"] = new_val
        result["recommendation_text"] = "已成功解析日期格式，使用系统解析结果"
        result["auto_fixable"] = True
        result["requires_business_update"] = False

    elif issue_code == "BENEFIT_VALUE_PARSEABLE":
        result["recommended_action"] = RecommendedAction.USE_PARSED_VALUE.value
        result["recommended_value"] = new_val
        result["recommendation_text"] = "已成功解析五险一金方案，使用系统解析结果"
        result["auto_fixable"] = True
        result["requires_business_update"] = False

    elif issue_code in ("TEXT_WHITESPACE_NORMALIZATION", "FULL_WIDTH_CHARACTER_NORMALIZATION"):
        result["recommended_action"] = RecommendedAction.USE_NORMALIZED_VALUE.value
        result["recommended_value"] = new_val
        result["recommendation_text"] = "使用系统标准化后的文本值"
        result["auto_fixable"] = True
        result["requires_business_update"] = False

    elif issue_code == "MISSING_HIRE_DATE":
        result["recommended_action"] = RecommendedAction.MANUAL_INPUT_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工确认，无法批量处理"
        result["auto_fixable"] = False

    elif issue_code == "MISSING_REGULARIZATION_DATE":
        result["recommended_action"] = RecommendedAction.MANUAL_INPUT_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工确认，无法批量处理"
        result["auto_fixable"] = False

    elif issue_code in ("IDENTITY_BIRTH_DATE_CONFLICT", "GENDER_IDENTITY_CONFLICT"):
        result["recommended_action"] = RecommendedAction.MANUAL_CONFIRMATION_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工判断，无法批量处理"
        result["auto_fixable"] = False

    elif issue_code in ("EMPLOYEE_MATCH_CONFLICT", "DUPLICATE_EMPLOYEE_NAME",
                        "DUPLICATE_NAME_IN_EXCEL", "MULTIPLE_DB_MATCH", "INACTIVE_EMPLOYEE"):
        result["recommended_action"] = RecommendedAction.MANUAL_MAPPING_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工选择匹配员工，无法批量处理"
        result["auto_fixable"] = False

    elif issue_code in ("NEW_DEPARTMENT", "NEW_POSITION", "NEW_TEAM"):
        result["recommended_action"] = RecommendedAction.MANUAL_MAPPING_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工映射组织字典，无法批量处理"
        result["auto_fixable"] = False

    elif issue_code == "REHIRE_SCENARIO":
        result["recommended_action"] = RecommendedAction.MANUAL_CONFIRMATION_REQUIRED.value
        result["recommendation_text"] = "已离职员工重新入职，需要人工确认"
        result["auto_fixable"] = False
        result["requires_business_update"] = True

    elif issue_code in ("CONTRACT_CHANGE", "NEW_BANK_ACCOUNT", "NEW_ALIPAY_ACCOUNT",
                        "SALARY_CHANGE", "POSSIBLE_REEMPLOYMENT", "PENDING_SEPARATION"):
        result["recommended_action"] = RecommendedAction.MANUAL_CONFIRMATION_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工确认，无法批量处理"
        result["auto_fixable"] = False
        result["requires_business_update"] = True

    elif issue_code == "UNKNOWN_BENEFIT_POLICY":
        result["recommended_action"] = RecommendedAction.MANUAL_CONFIRMATION_REQUIRED.value
        result["recommendation_text"] = "五险一金方案无法识别，需要人工确认"
        result["auto_fixable"] = False
        result["requires_business_update"] = True

    elif issue_code == "INVALID_PROBATION_MONTHS":
        result["recommended_action"] = RecommendedAction.MANUAL_INPUT_REQUIRED.value
        result["recommendation_text"] = "试用期月数不合法，需要人工输入有效值"
        result["auto_fixable"] = False

    elif issue_code == "NAME_EMPTY":
        result["recommended_action"] = RecommendedAction.MANUAL_INPUT_REQUIRED.value
        result["recommendation_text"] = "姓名为空，需要人工补全"
        result["auto_fixable"] = False

    elif issue_code in ("MISSING_REQUIRED_FIELD", "EMPLOYMENT_FORM_REGULARIZATION_CONFLICT"):
        result["recommended_action"] = RecommendedAction.MANUAL_INPUT_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工确认处理"
        result["auto_fixable"] = False

    elif issue_code in ("SALARY_UNPARSABLE", "PDP_CONTENT_SUSPICIOUS",
                        "BENEFIT_TEXT_UNRECOGNIZED"):
        result["recommended_action"] = RecommendedAction.MANUAL_INPUT_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工确认处理"
        result["auto_fixable"] = False

    else:
        # 未知问题代码：保守处理，不让自动处理
        result["recommended_action"] = RecommendedAction.MANUAL_CONFIRMATION_REQUIRED.value
        result["recommendation_text"] = "该问题需要人工确认，无法批量处理"
        result["auto_fixable"] = False

    return result


def enrich_issue_list(issues: list[dict]) -> list[dict]:
    """批量添加推荐处理信息。"""
    return [enrich_issue_with_recommendation(iss) for iss in issues]


# ============================================================
# 辅助
# ============================================================


def _format_value(value: Any) -> str | None:
    """将任意值格式化为字符串显示。"""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value[:200]
    try:
        return json.dumps(value, ensure_ascii=False, default=str)[:200]
    except (TypeError, ValueError):
        return str(value)[:200]

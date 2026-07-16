"""花名册生命周期统一评估器。

所有模块（预览、提交、修复）使用同一套规则判断员工的生命周期状态。
禁止预览和提交各写一套不同规则。

评估规则（P0）：
1. Excel 用工形式决定 employment_type、probation_status_hint 和 work_mode。
2. 统一生命周期基于 employment_type + 转正日期 + 用工形式综合判断。
3. 正式员工缺转正日期保持 REGULARIZED 状态，创建待确认事项。
4. 试用但转正日期已到达 → 按已转正处理，创建状态冲突警告。
5. 绝不根据试用期到期自动转正。
6. 已转正员工不生成试用期跟进任务。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from ..enums import (
    EmploymentStatus,
    EmploymentType,
    IssueSeverity,
    ProbationStatus,
    WorkMode,
)


def evaluate_roster_lifecycle(
    normalized_data: dict[str, Any],
    import_mode: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """花名册行生命周期统一评估。

    Args:
        normalized_data: 标准化后的行数据。
        import_mode: 导入模式（INITIALIZE / SYNC）。
        today: 评估基准日期，默认 date.today()。

    Returns:
        dict: 包含 employment_type / employment_status / probation_status /
              actual_hire_date / expected_regularization_date /
              actual_regularization_date / probation_months /
              should_create_probation_tasks / issues 等字段。
    """
    if today is None:
        today = date.today()

    issues: list[dict] = []

    # ── 1. 用工形式解析 ──
    raw_employment_form = str(normalized_data.get("employment_type") or "").strip()
    employment_type, probation_hint, work_mode = _parse_employment_form(raw_employment_form)

    # ── 2. 入职日期 ──
    hire_date = _parse_date_value(normalized_data.get("hire_date"))
    actual_hire_date = hire_date

    # ── 3. 转正日期 ──
    raw_reg_date = normalized_data.get("regularization_date")
    reg_date = _parse_date_value(raw_reg_date)

    # ── 4. 试用期月数 ──
    raw_pm = normalized_data.get("probation_months")

    # ── 5. 生命状态判断 ──
    is_initialize_mode = import_mode and str(import_mode).upper() == "INITIALIZE"
    employment_status = EmploymentStatus.ACTIVE if is_initialize_mode else EmploymentStatus.PENDING

    # 5a. 全职员工（正式/试用）
    if employment_type == EmploymentType.FORMAL:
        result = _evaluate_formal_employee(
            probation_hint=probation_hint,
            reg_date=reg_date,
            hire_date=hire_date,
            raw_pm=raw_pm,
            today=today,
            issues=issues,
        )
        probation_status = result["probation_status"]
        actual_regularization_date = result["actual_regularization_date"]
        expected_regularization_date = result["expected_regularization_date"]
        probation_months = result["probation_months"]
        should_create_probation_tasks = result["should_create_probation_tasks"]

    else:
        # 非正式员工（实习、外包、合作、其他）
        probation_status = ProbationStatus.REGULARIZED
        actual_regularization_date = None
        expected_regularization_date = None
        probation_months = _safe_parse_int(raw_pm) or 0
        should_create_probation_tasks = False

    # ── 6. 入职日期在未来 ──
    if hire_date and hire_date > today:
        employment_status = EmploymentStatus.PENDING

    # ── 7. 试用期月数 1-6 校验 ──
    _validate_probation_months_range(raw_pm, probation_months, issues)

    # ── 8. 年龄校验 ──
    _check_age_mismatch(normalized_data, today, issues)

    # ── 9. 司龄校验 ──
    _check_work_age_mismatch(normalized_data, today, issues)

    # ── 10. 姓名校验 ──
    _check_name(normalized_data, issues)

    # ── 11. 部门/岗位/地区为空 ──
    _check_required_fields(normalized_data, issues)

    # ── 12. 五险一金 ──
    _check_benefit_issues(normalized_data, issues)

    # ── 收拢结果 ──
    return {
        "employment_type": employment_type.value if employment_type else None,
        "employment_status": employment_status.value if employment_status else None,
        "probation_status": probation_status.value if probation_status else None,
        "work_mode": work_mode.value if work_mode else None,
        "actual_hire_date": _serialize_date(actual_hire_date),
        "expected_hire_date": _serialize_date(normalized_data.get("expected_hire_date")),
        "probation_months": probation_months,
        "probation_start_date": _serialize_date(hire_date) if probation_status
            in (ProbationStatus.IN_PROGRESS, ProbationStatus.REGULARIZED) and hire_date else None,
        "expected_regularization_date": _serialize_date(expected_regularization_date),
        "actual_regularization_date": _serialize_date(actual_regularization_date),
        "should_create_probation_tasks": should_create_probation_tasks,
        "raw_employment_form": raw_employment_form,
        "issues": issues,
    }


def _parse_employment_form(
    raw: str,
) -> tuple[EmploymentType, str | None, WorkMode | None]:
    """解析用工形式，拆分为 employment_type / probation_hint / work_mode。

    映射规则：
        "正式" → FORMAL, REGULARIZED, None
        "试用" → FORMAL, IN_PROGRESS, None
        "实习" → INTERN, None, None
        含"外包" → OUTSOURCED, None, None
        "远程" → FORMAL, None, REMOTE
        其他 → OTHER, None, None
    """
    if not raw:
        return EmploymentType.FORMAL, None, None

    text = raw.strip().lower()

    if text == "正式":
        return EmploymentType.FORMAL, "REGULARIZED", None
    if text == "试用":
        return EmploymentType.FORMAL, "IN_PROGRESS", None
    if "实习" in text:
        return EmploymentType.INTERN, None, None
    if "外包" in text:
        return EmploymentType.OUTSOURCED, None, None
    if text == "远程" or text == "remote":
        return EmploymentType.FORMAL, None, WorkMode.REMOTE
    if text in ("合作", "cooperation"):
        return EmploymentType.COOPERATION, None, None

    return EmploymentType.OTHER, None, None


def _evaluate_formal_employee(
    probation_hint: str | None,
    reg_date: date | None,
    hire_date: date | None,
    raw_pm: Any,
    today: date,
    issues: list[dict],
) -> dict[str, Any]:
    """正式员工生命周期评估。

    核心规则：
    - Excel 写"正式" → 已转正，无论是否有转正日期。
    - Excel 写"试用" → 试用中，但转正日期已到达时按已转正处理。
    """
    effective_probation_hint = probation_hint

    # 如果转正日期不晚于今天，按已转正处理
    if reg_date and reg_date <= today:
        if probation_hint == "IN_PROGRESS":
            issues.append({
                "issue_code": "EMPLOYMENT_FORM_REGULARIZATION_CONFLICT",
                "severity": IssueSeverity.WARNING.value,
                "title": "用工形式与转正日期冲突",
                "message": (
                    f"花名册填写「试用」，但转正日期（{reg_date.isoformat()}）"
                    f"已到达，系统已按正式员工初始化。"
                ),
                "field_key": "regularization_date",
                "old_value": None,
                "new_value": reg_date.isoformat(),
                "allowed_actions": ["ACCEPT", "IGNORE"],
            })
        effective_probation_hint = "REGULARIZED"

    is_regularized = effective_probation_hint == "REGULARIZED"

    if is_regularized:
        # ── 已转正 ──
        actual_reg_date = reg_date
        expected_reg_date = reg_date
        probation_months = _safe_parse_int(raw_pm) or 0
        probation_status = ProbationStatus.REGULARIZED
        should_create_tasks = False

        # 缺少转正日期
        if not actual_reg_date:
            issues.append({
                "issue_code": "MISSING_REGULARIZATION_DATE",
                "severity": IssueSeverity.WARNING.value,
                "title": "正式员工缺少转正日期",
                "message": (
                    "该员工用工形式为「正式」，但缺少转正日期。"
                    "系统已按正式员工初始化，请补充转正日期。"
                ),
                "field_key": "regularization_date",
                "old_value": None,
                "new_value": None,
                "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
            })
    else:
        # ── 试用期 ──
        probation_months = _safe_parse_int(raw_pm) or 3
        probation_status = ProbationStatus.IN_PROGRESS
        should_create_tasks = True

        if reg_date:
            expected_reg_date = reg_date
        elif hire_date:
            expected_reg_date = _calculate_regularization_date(hire_date, probation_months)
        else:
            expected_reg_date = None

        actual_reg_date = None

    return {
        "probation_status": probation_status,
        "actual_regularization_date": actual_reg_date,
        "expected_regularization_date": expected_reg_date,
        "probation_months": probation_months,
        "should_create_probation_tasks": should_create_tasks,
    }


def _validate_probation_months_range(raw_pm: Any, resolved_months: int, issues: list[dict]) -> None:
    """校验试用期月数是否在 1-6 范围内。"""
    if raw_pm is None:
        return
    try:
        pm = int(raw_pm)
        if pm <= 0:
            issues.append({
                "issue_code": "INVALID_PROBATION_MONTHS",
                "severity": IssueSeverity.BLOCKER.value,
                "title": "试用期月份数不合法",
                "message": f"试用期月数必须为 1-6 个月，当前值：{pm}。",
                "field_key": "probation_months",
                "old_value": None,
                "new_value": str(pm),
                "allowed_actions": ["MODIFY_VALUE"],
            })
        elif pm > 6:
            issues.append({
                "issue_code": "INVALID_PROBATION_MONTHS",
                "severity": IssueSeverity.BLOCKER.value,
                "title": "试用期月份数超过最大限制",
                "message": f"试用期 {pm} 个月超过最大允许值 6 个月，请确认。",
                "field_key": "probation_months",
                "old_value": None,
                "new_value": str(pm),
                "allowed_actions": ["MODIFY_VALUE"],
            })
    except (ValueError, TypeError):
        issues.append({
            "issue_code": "INVALID_PROBATION_MONTHS",
            "severity": IssueSeverity.BLOCKER.value,
            "title": "试用期月份数无效",
            "message": f"试用期月份数「{raw_pm}」无法解析为整数。",
            "field_key": "probation_months",
            "old_value": None,
            "new_value": str(raw_pm),
            "allowed_actions": ["MODIFY_VALUE"],
        })


def _check_age_mismatch(data: dict, today: date, issues: list[dict]) -> None:
    """校验年龄与出生日期是否一致。"""
    birth_date_raw = data.get("birth_date")
    age_raw = data.get("age")
    if not birth_date_raw or age_raw is None:
        return
    try:
        bd = _parse_date_value(birth_date_raw)
        declared_age = int(age_raw)
        if bd is not None:
            computed_age = (
                today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            )
            if abs(computed_age - declared_age) > 1:
                issues.append({
                    "issue_code": "AGE_MISMATCH",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "年龄与出生日期不符",
                    "message": (
                        f"根据出生日期计算年龄约 {computed_age} 岁，"
                        f"但申报年龄为 {declared_age} 岁，请核实。"
                    ),
                    "field_key": "birth_date",
                    "old_value": None,
                    "new_value": _serialize_date(birth_date_raw),
                    "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
                })
    except (ValueError, TypeError):
        pass


def _check_work_age_mismatch(data: dict, today: date, issues: list[dict]) -> None:
    """校验司龄与入职日期是否一致。"""
    hire_date_raw = data.get("hire_date")
    work_age_raw = data.get("work_age")
    if not hire_date_raw or work_age_raw is None:
        return
    try:
        hd = _parse_date_value(hire_date_raw)
        declared_work_age = float(work_age_raw)
        if hd is not None:
            computed_years = (today - hd).days / 365.25
            if computed_years < declared_work_age - 1:
                issues.append({
                    "issue_code": "WORK_AGE_MISMATCH",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "工龄与入职日期不符",
                    "message": (
                        f"根据入职日期计算的在职年限约 {computed_years:.1f} 年，"
                        f"但申报工龄为 {declared_work_age} 年。"
                        f"如包含外部工龄，请忽略此警告。"
                    ),
                    "field_key": "hire_date",
                    "old_value": None,
                    "new_value": _serialize_date(hire_date_raw),
                    "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
                })
    except (ValueError, TypeError):
        pass


def _check_name(data: dict, issues: list[dict]) -> None:
    """校验姓名字段。"""
    name = data.get("name")
    if not name or (isinstance(name, str) and not name.strip()):
        issues.append({
            "issue_code": "NAME_EMPTY",
            "severity": IssueSeverity.BLOCKER.value,
            "title": "姓名为空",
            "message": "姓名字段为空，无法完成匹配。",
            "field_key": "name",
            "old_value": None,
            "new_value": None,
            "allowed_actions": ["SKIP_ROW", "MODIFY_VALUE"],
        })


def _check_required_fields(data: dict, issues: list[dict]) -> None:
    """校验必填任职字段。"""
    hire_date = data.get("hire_date")
    if hire_date is None or (isinstance(hire_date, str) and not hire_date.strip()):
        issues.append({
            "issue_code": "MISSING_REQUIRED_FIELD",
            "severity": IssueSeverity.WARNING.value,
            "title": "缺少入职日期",
            "message": (
                "入职日期为空。新员工仍会创建员工档案，"
                "但不会创建任职记录。请导入后补充入职日期。"
            ),
            "field_key": "hire_date",
            "old_value": None,
            "new_value": None,
            "allowed_actions": ["SKIP_ROW", "MODIFY_VALUE", "IGNORE"],
        })

    if not data.get("department"):
        issues.append({
            "issue_code": "MISSING_REQUIRED_FIELD",
            "severity": IssueSeverity.INFO.value,
            "title": "部门为空",
            "message": "部门字段为空，建议补充。",
            "field_key": "department",
            "old_value": None,
            "new_value": None,
            "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
        })

    if not data.get("work_city"):
        issues.append({
            "issue_code": "MISSING_REQUIRED_FIELD",
            "severity": IssueSeverity.INFO.value,
            "title": "工作地区为空",
            "message": "工作地区字段为空，建议补充。",
            "field_key": "work_city",
            "old_value": None,
            "new_value": None,
            "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
        })


def _check_benefit_issues(data: dict, issues: list[dict]) -> None:
    """校验五险一金相关问题。"""
    benefit_parse_status = data.get("benefit_parse_status")
    if benefit_parse_status == "UNRECOGNIZED":
        issues.append({
            "issue_code": "BENEFIT_TEXT_UNRECOGNIZED",
            "severity": IssueSeverity.WARNING.value,
            "title": "五险一金缴纳方案无法识别",
            "message": "五险一金原文无法自动解析。",
            "field_key": "benefit_raw_text",
            "old_value": data.get("benefit_raw_text"),
            "new_value": None,
            "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
        })

    # 转正缴纳但缺少转正日期
    social_policy = data.get("social_insurance_policy") or ""
    if "REGULARIZATION" in str(social_policy).upper():
        reg_date = data.get("regularization_date")
        if not reg_date:
            issues.append({
                "issue_code": "BENEFIT_TEXT_UNRECOGNIZED",
                "severity": IssueSeverity.INFO.value,
                "title": "五险转正缴纳但缺少转正日期",
                "message": "社保方案为「转正缴纳」，但缺少转正日期。",
                "field_key": "social_insurance_policy",
                "old_value": None,
                "new_value": str(social_policy),
                "allowed_actions": ["MODIFY_VALUE", "IGNORE"],
            })


# ============================================================
# 工具函数
# ============================================================


def _parse_date_value(value: Any) -> date | None:
    """解析日期值。"""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
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


def _safe_parse_int(value: Any, default: int = 3) -> int:
    """安全解析整数。"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _calculate_regularization_date(hire_date: date, months: int) -> date:
    """计算预计转正日期。"""
    month = hire_date.month + months
    year = hire_date.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    day = min(hire_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _serialize_date(value: Any) -> str | None:
    """序列化日期为 ISO 字符串。"""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None

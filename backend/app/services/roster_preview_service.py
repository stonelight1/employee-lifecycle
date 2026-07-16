"""花名册导入预览服务。

字段分类全部使用统一策略（roster_field_policy），
不再各自维护字段列表。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    AccountStatus,
    AccountType,
    EmployeeStatus,
    EmploymentStatus,
    IssueAction,
    IssueSeverity,
    ProbationStatus,
    ResolutionStatus,
    RosterBatchStatus,
    RosterImportMode,
    RosterRowStatus,
)
from ..exceptions import ResourceNotFound
from ..models.assessment import EmployeeAssessment
from ..models.compensation import CompensationRecord
from ..models.contract import EmploymentContract
from ..models.employee import Employee
from ..models.employee_profile import EmployeeProfile
from ..models.employment import EmploymentRecord
from ..models.financial_account import EmployeeFinancialAccount
from ..models.roster_batch import RosterImportBatch
from ..models.roster_issue import RosterImportIssue
from ..models.roster_row import RosterImportRow
from .employee_service import resolve_lifecycle_stage
from .normalize import normalize_name
from .roster_cooperation import is_cooperation_region
from .roster_field_policy import (
    FieldUpdateMode as PolicyMode,
    get_all_field_keys,
    get_field_policy,
)

try:
    from .roster_mapping_service import resolve_value_alias
except ImportError:
    resolve_value_alias = None


# ============================================================
# 使用统一策略
# ============================================================

# 自动更新字段
AUTO_UPDATE_FIELDS = sorted(get_all_field_keys() - {f for f in get_all_field_keys()
    if (p := get_field_policy(f)) and p.update_mode in (
        PolicyMode.CONFIRM_BEFORE_UPDATE,
        PolicyMode.APPEND_RECORD,
        PolicyMode.CALCULATED_ONLY,
        PolicyMode.RAW_ONLY,
        PolicyMode.IGNORE,
    )})

# 需确认字段（包含 APPEND_RECORD）
CONFIRMATION_FIELDS = sorted({f for f in get_all_field_keys()
    if (p := get_field_policy(f)) and p.update_mode in (
        PolicyMode.CONFIRM_BEFORE_UPDATE,
        PolicyMode.APPEND_RECORD,
    )})

# ============================================================
# 标签映射
# ============================================================

_FIELD_LABELS: dict[str, str] = {}
for fk in get_all_field_keys():
    policy = get_field_policy(fk)
    if policy and policy.labels:
        _FIELD_LABELS[fk] = policy.labels[0]

# 补充不在策略中的字段
_FIELD_LABELS.update({
    "hire_date": "入职日期",
    "probation_months": "试用期月数",
    "regularization_date": "转正日期",
    "employment_type": "用工类型",
    "raw_salary_text": "薪酬文本",
    "assessment_result": "测评结果",
    "name": "姓名",
})

_ACTION_LABELS: dict[RosterRowStatus, list[str]] = {
    RosterRowStatus.NEW: [IssueAction.ACCEPT.value, IssueAction.SKIP_ROW.value],
    RosterRowStatus.UPDATE: [IssueAction.ACCEPT.value, IssueAction.SKIP_ROW.value],
    RosterRowStatus.UNCHANGED: [],
    RosterRowStatus.NEEDS_CONFIRMATION: [IssueAction.ACCEPT.value, IssueAction.SKIP_ROW.value],
    RosterRowStatus.ERROR: [IssueAction.SKIP_ROW.value],
    RosterRowStatus.SKIPPED: [],
}

_BENEFIT_CLEARABLE_FIELDS = {
    "social_insurance_start_date",
    "housing_fund_start_date",
}


# ============================================================
# 公开接口
# ============================================================


def generate_preview(db: DBSession, batch_id: int) -> dict:
    """生成花名册导入预览。

    使用批量加载消除 N+1 查询。
    """
    batch = _load_batch(db, batch_id)
    rows = _load_rows(db, batch_id)
    if not rows:
        raise ValueError("批次中没有数据行，无法预览")

    # 批量匹配员工
    all_names = sorted({row.normalized_name for row in rows if row.normalized_name})
    employee_map = _match_employees_batch(db, all_names) if all_names else {}

    # 批量加载员工当前状态（消除 N+1）
    all_employee_ids = []
    for name_key, emp_list in employee_map.items():
        all_employee_ids.extend(e.id for e in emp_list if not e.is_deleted)
    batch_state_map = _batch_load_current_states(db, all_employee_ids) if all_employee_ids else {}

    # 构建姓名 -> 行列表（排除合作行，避免合作行参与重名判断）
    all_rows_by_name: dict[str, list[RosterImportRow]] = {}
    cooperation_row_ids: set[int] = set()
    for row in rows:
        n = row.normalized_name or ""
        # 检查是否合作地区
        new_data = _parse_row_data(row)
        if is_cooperation_region(new_data):
            cooperation_row_ids.add(row.id)
            row.row_status = RosterRowStatus.SKIPPED
            row.planned_actions_json = json.dumps({
                "action": "SKIP",
                "reason_code": "REGION_COOPERATION",
                "reason": "地区为合作，不纳入员工生命周期系统",
            }, ensure_ascii=False)
            continue
        all_rows_by_name.setdefault(n, []).append(row)

    # 逐行处理
    preview_rows: list[dict] = []
    all_issues: list[dict] = []

    summary = {
        "new_count": 0,
        "update_count": 0,
        "unchanged_count": 0,
        "confirmation_count": 0,
        "error_count": 0,
        "skipped_count": 0,
        "blocker_count": 0,
        "warning_count": 0,
        "total_rows": len(rows),
    }

    for row in rows:
        # 合作行已经跳过，直接汇总
        if row.id in cooperation_row_ids:
            _accumulate_summary(summary, RosterRowStatus.SKIPPED, [])
            row_preview = {
                "row_no": row.row_no,
                "employee_id": None,
                "normalized_name": row.normalized_name,
                "matched_employee_name": None,
                "row_status": RosterRowStatus.SKIPPED.value,
                "diff_fields": [],
                "issues": [{
                    "issue_code": "REGION_COOPERATION",
                    "severity": "INFO",
                    "title": "地区为合作，不纳入系统",
                    "message": "该员工所在地区标记为「合作」，"
                    "跳过导入员工生命周期系统。",
                    "field_key": "work_city",
                    "allowed_actions": [],
                }],
                "can_skip": False,
                "actions": [],
            }
            preview_rows.append(row_preview)
            continue

        matched = employee_map.get(row.normalized_name, [])
        current_state = batch_state_map.get(matched[0].id, {}) if len(matched) == 1 else {}

        row_status, diff_list, issue_list = _classify_row(
            db,
            row,
            matched,
            all_rows_by_name,
            current_state,
        )

        for iss in issue_list:
            iss["row_id"] = row.id
            if matched and len(matched) == 1:
                iss.setdefault("employee_id", matched[0].id)

        row.row_status = row_status
        if diff_list:
            row.diff_json = json.dumps(diff_list, ensure_ascii=False, default=str)

        _accumulate_summary(summary, row_status, issue_list)

        matched_employee = matched[0] if len(matched) == 1 else None
        row_preview = {
            "row_no": row.row_no,
            "employee_id": matched_employee.id if matched_employee else None,
            "normalized_name": row.normalized_name,
            "matched_employee_name": matched_employee.name if matched_employee else None,
            "row_status": row_status.value,
            "diff_fields": diff_list,
            "issues": [_issue_to_dict(iss) for iss in issue_list],
            "can_skip": row_status
            in (RosterRowStatus.NEW, RosterRowStatus.NEEDS_CONFIRMATION, RosterRowStatus.ERROR),
            "actions": list(_ACTION_LABELS.get(row_status, [])),
        }
        preview_rows.append(row_preview)
        all_issues.extend(issue_list)

    # 更新批次
    _update_batch_summary(batch, summary)
    batch.batch_status = (
        RosterBatchStatus.WAITING_RESOLUTION
        if summary.get("blocker_count", 0) > 0
        else RosterBatchStatus.READY
    )
    db.flush()

    _save_issues(db, batch_id, all_issues)
    db.flush()

    current_mappings = _get_current_mappings(batch)

    return {
        "batch_id": batch.id,
        "mode": _enum_value(batch.mode),
        "summary": summary,
        "rows": preview_rows,
        "issues": [_issue_to_dict(iss) for iss in all_issues],
        "current_mappings": current_mappings,
    }


def update_batch_status(db: DBSession, batch_id: int, status: RosterBatchStatus) -> None:
    batch = _load_batch(db, batch_id)
    batch.batch_status = status
    db.flush()


# ============================================================
# 批量加载员工当前状态（消除 N+1）
# ============================================================


def _batch_load_current_states(
    db: DBSession,
    employee_ids: list[int],
) -> dict[int, dict[str, Any]]:
    """批量加载所有员工的当前系统状态。

    一次性查询所有员工的 profile / employment / contract / account，
    在内存中组装。
    """
    if not employee_ids:
        return {}

    # Employee
    employees = {
        e.id: e for e in db.query(Employee).filter(
            Employee.id.in_(employee_ids), Employee.is_deleted == False
        ).all()
    }

    # Profile
    profiles = {}
    for p in db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id.in_(employee_ids),
        EmployeeProfile.is_deleted == False,
    ).all():
        profiles[p.employee_id] = p

    # Employment（最新一条）
    employments = {}
    all_emps = db.query(EmploymentRecord).filter(
        EmploymentRecord.employee_id.in_(employee_ids),
        EmploymentRecord.is_deleted == False,
    ).order_by(EmploymentRecord.employment_seq.desc()).all()
    for emp in all_emps:
        if emp.employee_id not in employments:
            employments[emp.employee_id] = emp

    # Contract（最新一条）
    contracts = {}
    all_contracts = db.query(EmploymentContract).filter(
        EmploymentContract.employee_id.in_(employee_ids),
        EmploymentContract.is_deleted == False,
    ).order_by(EmploymentContract.id.desc()).all()
    for c in all_contracts:
        if c.employee_id not in contracts:
            contracts[c.employee_id] = c

    # Financial accounts
    accounts = {eid: {"bank": None, "alipay": None} for eid in employee_ids}
    for a in db.query(EmployeeFinancialAccount).filter(
        EmployeeFinancialAccount.employee_id.in_(employee_ids),
        EmployeeFinancialAccount.account_status == AccountStatus.ACTIVE.value,
        EmployeeFinancialAccount.is_deleted == False,
    ).order_by(
        EmployeeFinancialAccount.is_primary.desc(),
        EmployeeFinancialAccount.id.desc(),
    ).all():
        if a.employee_id not in accounts:
            accounts[a.employee_id] = {"bank": None, "alipay": None}
        if a.account_type == AccountType.BANK.value and accounts[a.employee_id]["bank"] is None:
            accounts[a.employee_id]["bank"] = a
        if a.account_type == AccountType.ALIPAY.value and accounts[a.employee_id]["alipay"] is None:
            accounts[a.employee_id]["alipay"] = a

    _PROFILE_FIELDS = [
        "identity_card", "gender", "birth_date",
        "household_registration", "residence_address", "household_type",
        "graduation_school", "major", "education_level",
        "social_insurance_status", "housing_fund_status",
        "social_insurance_policy", "housing_fund_policy",
        "social_insurance_start_date", "housing_fund_start_date",
        "benefit_raw_text",
    ]

    result: dict[int, dict[str, Any]] = {}
    for eid in employee_ids:
        emp = employees.get(eid)
        if not emp:
            continue

        state: dict[str, Any] = {
            "name": emp.name,
            "normalized_name": emp.normalized_name,
            "mobile": emp.mobile,
            "email": emp.email,
            "employee_no": emp.employee_no,
        }

        profile = profiles.get(eid)
        for field in _PROFILE_FIELDS:
            state[field] = getattr(profile, field, None) if profile else None

        employment = employments.get(eid)
        if employment:
            state["work_city"] = employment.work_city
            state["work_mode"] = _enum_value(employment.work_mode) if employment.work_mode else None
            state["team_name"] = employment.team_name
            state["hire_date"] = employment.hire_date
            state["employment_status"] = _enum_value(employment.employment_status) if employment.employment_status else None
            state["probation_months"] = employment.probation_months
            state["regularization_date"] = employment.regularization_date
            state["employment_type"] = _enum_value(employment.employment_type) if employment.employment_type else None
        else:
            for f in ("work_city", "work_mode", "team_name", "hire_date", "employment_status",
                      "probation_months", "regularization_date", "employment_type"):
                state[f] = None

        contract = contracts.get(eid)
        if contract:
            state["contract_status"] = contract.contract_status
            state["signing_company"] = contract.signing_company
            state["contract_type"] = _enum_value(contract.contract_type) if contract.contract_type else None

        e_accounts = accounts.get(eid, {"bank": None, "alipay": None})
        state["bank_card"] = e_accounts["bank"].account_no if e_accounts["bank"] else None
        state["alipay"] = e_accounts["alipay"].account_no if e_accounts["alipay"] else None

        result[eid] = state

    return result


# ============================================================
# 员工批量匹配
# ============================================================


def _match_employees_batch(
    db: DBSession, names: list[str]
) -> dict[str, list[Employee]]:
    if not names:
        return {}

    employees = (
        db.query(Employee)
        .filter(
            Employee.normalized_name.in_(names),
            Employee.is_deleted == False,
            Employee.employee_status != EmployeeStatus.ENTRY_ERROR.value,
        )
        .all()
    )

    result: dict[str, list[Employee]] = {}
    for emp in employees:
        result.setdefault(emp.normalized_name, []).append(emp)
    return result


# ============================================================
# 行分类
# ============================================================


def _classify_row(
    db: DBSession,
    row: RosterImportRow,
    matched_employees: list[Employee],
    all_rows_by_name: dict[str, list[RosterImportRow]],
    current_state: dict[str, Any] | None = None,
) -> tuple[RosterRowStatus, list[dict], list[dict]]:
    """对单行数据进行分类。"""
    name = row.normalized_name
    issues: list[dict] = []

    # 姓名为空
    if not name:
        issues.append(
            _build_issue(
                issue_code="NAME_EMPTY",
                severity=IssueSeverity.BLOCKER,
                title="姓名为空",
                message="该行姓名字段为空，无法匹配员工。请手动补全姓名或跳过该行。",
                field_key="name",
                allowed_actions=[IssueAction.SKIP_ROW.value, IssueAction.MODIFY_VALUE.value],
            )
        )
        return (RosterRowStatus.ERROR, [], issues)

    # Excel 内重复姓名
    same_name_rows = all_rows_by_name.get(name, [])
    if len(same_name_rows) > 1:
        issues.append(
            _build_issue(
                issue_code="DUPLICATE_NAME_IN_EXCEL",
                severity=IssueSeverity.BLOCKER,
                title="Excel 中存在重复姓名",
                message=f"姓名「{name}」在 Excel 中出现了 {len(same_name_rows)} 次，"
                f"无法自动确定匹配目标（行号：{','.join(str(r.row_no) for r in same_name_rows)}）。",
                field_key="name",
                allowed_actions=[IssueAction.SKIP_ROW.value, IssueAction.SELECT_EMPLOYEE.value],
            )
        )
        return (RosterRowStatus.ERROR, [], issues)

    # 筛选活跃匹配结果
    active_matched = [
        e for e in matched_employees
        if not e.is_deleted and e.employee_status != EmployeeStatus.ENTRY_ERROR.value
    ]

    # 多条匹配
    if len(active_matched) > 1:
        candidate_info = "; ".join(
            f"{e.name}(ID:{e.id}, no:{e.employee_no or '—'})" for e in active_matched
        )
        issues.append(
            _build_issue(
                issue_code="MULTIPLE_DB_MATCH",
                severity=IssueSeverity.BLOCKER,
                title="数据库中存在多条匹配",
                message=f"姓名「{name}」在数据库中匹配到多条员工记录：{candidate_info}。"
                f"请手动选择目标员工。",
                field_key="name",
                allowed_actions=[IssueAction.SKIP_ROW.value, IssueAction.SELECT_EMPLOYEE.value],
            )
        )
        return (RosterRowStatus.ERROR, [], issues)

    # 无匹配
    if len(active_matched) == 0:
        inactive = [
            e for e in matched_employees
            if e.is_deleted or e.employee_status == EmployeeStatus.ENTRY_ERROR.value
        ]
        if inactive:
            emp = inactive[0]
            issues.append(
                _build_issue(
                    issue_code="INACTIVE_EMPLOYEE",
                    severity=IssueSeverity.BLOCKER,
                    title="员工记录处于非活跃状态",
                    message=f"数据库中存在姓名「{name}」的记录（ID:{emp.id}），"
                    f"但该记录已{'删除' if emp.is_deleted else '标记为录入错误'}。"
                    f"无法自动匹配。",
                    field_key="name",
                    allowed_actions=[IssueAction.SKIP_ROW.value, IssueAction.CREATE_NEW_EMPLOYEE.value],
                )
            )
            return (RosterRowStatus.ERROR, [], issues)

        # NEW 行：入职日期为 WARNING，不是 BLOCKER
        return (RosterRowStatus.NEW, [], issues)

    # 精确匹配到一个
    employee = active_matched[0]

    # 已离职 → 重聘
    employment = _find_current_employment(db, employee.id)
    lifecycle_stage = (
        resolve_lifecycle_stage(employment) if employment else "UNKNOWN"
    )
    if employment and employment.employment_status == EmploymentStatus.SEPARATED:
        issues.append(
            _build_issue(
                issue_code="REHIRE_SCENARIO",
                severity=IssueSeverity.WARNING,
                title="已离职员工重新入职",
                message=f"员工「{employee.name}」当前任职状态为「已离职」，"
                f"导入将触发重新入职流程。",
                field_key=None,
                allowed_actions=[IssueAction.CONFIRM_REEMPLOYMENT.value, IssueAction.SKIP_ROW.value],
            )
        )

    # 使用传入的当前状态或重新查询
    if current_state is None:
        current_state = _get_current_state_single(db, employee)

    new_data = _parse_row_data(row)

    diff_list = _compute_diff(current_state, new_data)

    extra_issues = _generate_issues(
        row, matched_employees, None, diff_list, all_rows_by_name, new_data, current_state
    )
    issues.extend(extra_issues)

    # 决定最终状态
    if not diff_list:
        status = RosterRowStatus.UNCHANGED
    else:
        has_confirmation = any(
            d.get("change_type") == "NEEDS_CONFIRMATION" for d in diff_list
        )
        has_update = any(
            d.get("change_type") == "UPDATE" for d in diff_list
        )
        if has_confirmation:
            status = RosterRowStatus.NEEDS_CONFIRMATION
        elif has_update:
            status = RosterRowStatus.UPDATE
        else:
            status = RosterRowStatus.UNCHANGED

    return (status, diff_list, issues)


# ============================================================
# 单员工当前状态查询（回退用）
# ============================================================


def _get_current_state_single(db: DBSession, employee: Employee) -> dict:
    """获取单个员工的当前系统状态。"""
    return _batch_load_current_states(db, [employee.id]).get(employee.id, {})


def _find_current_employment(db: DBSession, employee_id: int) -> EmploymentRecord | None:
    return (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.desc())
        .first()
    )


# ============================================================
# 差异计算
# ============================================================


def _compute_diff(current: dict, new: dict) -> list[dict]:
    """计算当前值与新值的差异。"""
    diffs: list[dict] = []

    for field in AUTO_UPDATE_FIELDS:
        _append_diff_if_changed(diffs, field, current, new, "UPDATE")

    for field in CONFIRMATION_FIELDS:
        _append_diff_if_changed(diffs, field, current, new, "NEEDS_CONFIRMATION")

    return diffs


def _append_diff_if_changed(
    diffs: list[dict],
    field: str,
    current: dict,
    new: dict,
    change_type: str,
) -> None:
    """如果字段值发生了变化，追加一条差异记录。"""
    old_val = current.get(field)
    new_val = new.get(field)

    if new_val is None and not (
        field in _BENEFIT_CLEARABLE_FIELDS
        and new.get("benefit_parse_status") == "PARSED"
        and field in new
    ):
        return
    if isinstance(new_val, str) and not new_val.strip():
        return

    if _values_equal(old_val, new_val):
        return

    diffs.append(
        {
            "field_key": field,
            "field_label": _FIELD_LABELS.get(field, field),
            "old_value": _serialize_value(old_val),
            "new_value": _serialize_value(new_val),
            "change_type": change_type,
        }
    )


def _values_equal(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return _serialize_value(a) == _serialize_value(b)


def _serialize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).strip()
    return s if s else None


def _parse_row_data(row: RosterImportRow) -> dict:
    if not row.normalized_data_json:
        return {}
    try:
        data = json.loads(row.normalized_data_json)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ============================================================
# 问题生成
# ============================================================


def _generate_issues(
    row: RosterImportRow,
    matched_employees: list[Employee],
    row_status: RosterRowStatus | None,
    diff: list[dict],
    all_rows_by_name: dict[str, list[RosterImportRow]],
    new_data: dict[str, Any] | None = None,
    current_state: dict[str, Any] | None = None,
) -> list[dict]:
    """根据行数据、匹配结果和差异生成额外问题。"""
    issues: list[dict] = []
    name = row.normalized_name

    if new_data is None:
        new_data = _parse_row_data(row)

    employee = matched_employees[0] if len(matched_employees) == 1 else None

    if current_state is None:
        current_state = {}

    # ── 姓名规范校验（BLOCKER）──
    if not name:
        issues.append(
            _build_issue(
                issue_code="NAME_EMPTY",
                severity=IssueSeverity.BLOCKER,
                title="姓名为空",
                message="姓名字段为空，无法完成匹配。",
                field_key="name",
                allowed_actions=[IssueAction.SKIP_ROW.value, IssueAction.MODIFY_VALUE.value],
            )
        )

    # ── 试用期月份数校验（BLOCKER：1-6个月）──
    raw_pm = new_data.get("probation_months")
    if raw_pm is not None:
        try:
            pm = int(raw_pm)
            if pm <= 0:
                issues.append(
                    _build_issue(
                        issue_code="INVALID_PROBATION_MONTHS",
                        severity=IssueSeverity.BLOCKER,
                        title="试用期月份数不合法",
                        message=f"试用期月数必须为 1-6 个月，当前值：{pm}。",
                        field_key="probation_months",
                        old_value=current_state.get("probation_months"),
                        new_value=str(pm),
                        allowed_actions=[IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
                    )
                )
            elif pm > 6:
                issues.append(
                    _build_issue(
                        issue_code="INVALID_PROBATION_MONTHS",
                        severity=IssueSeverity.BLOCKER,
                        title="试用期月份数超过最大限制",
                        message=f"试用期 {pm} 个月超过最大允许值 6 个月，请确认。",
                        field_key="probation_months",
                        old_value=current_state.get("probation_months"),
                        new_value=str(pm),
                        allowed_actions=[IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
                    )
                )
        except (ValueError, TypeError):
            issues.append(
                _build_issue(
                    issue_code="INVALID_PROBATION_MONTHS",
                    severity=IssueSeverity.BLOCKER,
                    title="试用期月份数无效",
                    message=f"试用期月份数「{raw_pm}」无法解析为整数。",
                    field_key="probation_months",
                    old_value=current_state.get("probation_months"),
                    new_value=_serialize_value(raw_pm),
                    allowed_actions=[IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
                )
            )

    # ── 必填字段校验（WARNING，非 BLOCKER）──
    # 入职日期缺失创建 WARNING，不阻断
    hire_date = new_data.get("hire_date")
    if hire_date is None or (isinstance(hire_date, str) and not hire_date.strip()):
        # NEW 行缺少入职日期：WARNING（仍允许创建员工档案）
        # UPDATE 行缺少入职日期：不覆盖系统值
        issues.append(
            _build_issue(
                issue_code="MISSING_REQUIRED_FIELD",
                severity=IssueSeverity.WARNING,
                title="缺少入职日期",
                message="入职日期为空。新员工仍会创建员工档案，"
                "但不会创建任职记录。请导入后补充入职日期。",
                field_key="hire_date",
                allowed_actions=[IssueAction.SKIP_ROW.value, IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
            )
        )

    # ── 转正日期缺失提醒（WARNING）──
    emp_type = new_data.get("employment_type") or current_state.get(
        "employment_type"
    )
    if emp_type and _is_formal_employment(emp_type):
        reg_date = new_data.get("regularization_date") or current_state.get(
            "regularization_date"
        )
        if not reg_date:
            issues.append(
                _build_issue(
                    issue_code="MISSING_REGULARIZATION_DATE",
                    severity=IssueSeverity.WARNING,
                    title="正式员工缺少转正日期",
                    message="该员工用工类型为正式，但缺少转正日期。"
                    "导入后请及时补充转正日期。",
                    field_key="regularization_date",
                    allowed_actions=[IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
                )
            )

    # ── 年龄与出生日期交叉校验（WARNING）──
    birth_date_raw = new_data.get("birth_date") or current_state.get("birth_date")
    age_raw = new_data.get("age")
    if birth_date_raw and age_raw is not None:
        try:
            bd = _parse_date(birth_date_raw)
            declared_age = int(age_raw)
            if bd is not None:
                today = date.today()
                computed_age = (
                    today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                )
                if abs(computed_age - declared_age) > 1:
                    issues.append(
                        _build_issue(
                            issue_code="AGE_MISMATCH",
                            severity=IssueSeverity.WARNING,
                            title="年龄与出生日期不符",
                            message=f"根据出生日期计算年龄约 {computed_age} 岁，"
                            f"但申报年龄为 {declared_age} 岁，请核实。",
                            field_key="birth_date",
                            old_value=current_state.get("birth_date"),
                            new_value=_serialize_value(birth_date_raw),
                            allowed_actions=[IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
                        )
                    )
        except (ValueError, TypeError):
            pass

    # ── 工龄校验（WARNING）──
    hire_date_raw = new_data.get("hire_date") or current_state.get("hire_date")
    work_age_raw = new_data.get("work_age")
    if hire_date_raw and work_age_raw is not None:
        try:
            hd = _parse_date(hire_date_raw)
            declared_work_age = float(work_age_raw)
            if hd is not None:
                today = date.today()
                computed_years = (today - hd).days / 365.25
                if computed_years < declared_work_age - 1:
                    issues.append(
                        _build_issue(
                            issue_code="WORK_AGE_MISMATCH",
                            severity=IssueSeverity.WARNING,
                            title="工龄与入职日期不符",
                            message=f"根据入职日期计算的在职年限约 {computed_years:.1f} 年，"
                            f"但申报工龄为 {declared_work_age} 年。"
                            f"如包含外部工龄，请忽略此警告。",
                            field_key="hire_date",
                            old_value=current_state.get("hire_date"),
                            new_value=_serialize_value(hire_date_raw),
                            allowed_actions=[IssueAction.MODIFY_VALUE.value, IssueAction.IGNORE.value],
                        )
                    )
        except (ValueError, TypeError):
            pass

    # ── 薪酬文本解析警告（WARNING）──
    salary_text = new_data.get("raw_salary_text")
    if salary_text and isinstance(salary_text, str) and salary_text.strip():
        if not _looks_like_parsed_salary(salary_text):
            issues.append(
                _build_issue(
                    issue_code="SALARY_UNPARSABLE",
                    severity=IssueSeverity.WARNING,
                    title="薪酬文本可能无法自动解析",
                    message=f"薪酬文本「{salary_text[:100]}」格式不标准，"
                    f"系统可能无法完全自动解析。",
                    field_key="raw_salary_text",
                    new_value=salary_text[:200],
                    allowed_actions=[IssueAction.IGNORE.value, IssueAction.MODIFY_VALUE.value],
                )
            )

    benefit_parse_status = new_data.get("benefit_parse_status")
    if benefit_parse_status == "UNRECOGNIZED":
        issues.append(
            _build_issue(
                issue_code="BENEFIT_TEXT_UNRECOGNIZED",
                severity=IssueSeverity.WARNING,
                title="五险一金缴纳方案无法识别",
                message="五险一金原文无法自动解析。",
                field_key="benefit_raw_text",
                old_value=current_state.get("benefit_raw_text"),
                new_value=new_data.get("benefit_raw_text"),
                allowed_actions=["correct_manually", "ignore"],
            )
        )

    # ── PDP 测评内容可疑（WARNING）──
    pdp_text = new_data.get("pdp_result") or new_data.get("assessment_result")
    if pdp_text and isinstance(pdp_text, str) and pdp_text.strip():
        if _looks_suspicious_pdp(pdp_text):
            issues.append(
                _build_issue(
                    issue_code="PDP_CONTENT_SUSPICIOUS",
                    severity=IssueSeverity.WARNING,
                    title="PDP 测评内容疑似异常",
                    message=f"PDP 测评文本「{pdp_text[:100]}」看起来不符合预期的测评报告格式。",
                    field_key="pdp_result",
                    new_value=pdp_text[:200],
                    allowed_actions=[IssueAction.IGNORE.value, IssueAction.MODIFY_VALUE.value],
                )
            )

    return issues


# ============================================================
# 内部辅助
# ============================================================


def _build_issue(
    issue_code: str,
    severity: IssueSeverity,
    title: str,
    message: str | None = None,
    field_key: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    allowed_actions: list[str] | None = None,
    employee_id: int | None = None,
    row_id: int | None = None,
) -> dict:
    return {
        "issue_code": issue_code,
        "severity": severity.value,
        "title": title,
        "message": message,
        "field_key": field_key,
        "old_value": _serialize_value(old_value),
        "new_value": _serialize_value(new_value),
        "allowed_actions": allowed_actions or [],
        "employee_id": employee_id,
        "row_id": row_id,
    }


def _issue_to_dict(issue: dict) -> dict:
    return {
        "issue_code": issue.get("issue_code"),
        "severity": issue.get("severity"),
        "title": issue.get("title"),
        "message": issue.get("message"),
        "field_key": issue.get("field_key"),
        "old_value": issue.get("old_value"),
        "new_value": issue.get("new_value"),
        "allowed_actions": issue.get("allowed_actions", []),
        "row_no": issue.get("row_no"),
        "employee_name": issue.get("employee_name"),
    }


def _load_batch(db: DBSession, batch_id: int) -> RosterImportBatch:
    batch = (
        db.query(RosterImportBatch)
        .filter(
            RosterImportBatch.id == batch_id,
            RosterImportBatch.is_deleted == False,
        )
        .first()
    )
    if not batch:
        raise ResourceNotFound("导入批次不存在")

    allowed = (
        RosterBatchStatus.UPLOADED,
        RosterBatchStatus.MAPPING_REQUIRED,
        RosterBatchStatus.PREVIEW_READY,
    )
    if batch.batch_status not in allowed:
        raise ValueError(
            f"批次状态为 {batch.batch_status}，不允许预览。"
            f"允许预览的状态：{'、'.join(s.value for s in allowed)}"
        )
    return batch


def _load_rows(db: DBSession, batch_id: int) -> list[RosterImportRow]:
    return (
        db.query(RosterImportRow)
        .filter(RosterImportRow.batch_id == batch_id)
        .order_by(RosterImportRow.row_no.asc())
        .all()
    )


def _accumulate_summary(
    summary: dict,
    row_status: RosterRowStatus,
    issue_list: list[dict],
) -> None:
    key_map = {
        RosterRowStatus.NEW: "new_count",
        RosterRowStatus.UPDATE: "update_count",
        RosterRowStatus.UNCHANGED: "unchanged_count",
        RosterRowStatus.NEEDS_CONFIRMATION: "confirmation_count",
        RosterRowStatus.ERROR: "error_count",
        RosterRowStatus.SKIPPED: "skipped_count",
    }
    key = key_map.get(row_status)
    if key:
        summary[key] = summary.get(key, 0) + 1

    for iss in issue_list:
        sev = iss.get("severity")
        if sev == IssueSeverity.BLOCKER.value:
            summary["blocker_count"] = summary.get("blocker_count", 0) + 1
        elif sev == IssueSeverity.WARNING.value:
            summary["warning_count"] = summary.get("warning_count", 0) + 1


def _update_batch_summary(batch: RosterImportBatch, summary: dict) -> None:
    batch.total_rows = summary.get("total_rows", 0)
    batch.new_count = summary.get("new_count", 0)
    batch.update_count = summary.get("update_count", 0)
    batch.unchanged_count = summary.get("unchanged_count", 0)
    batch.confirmation_count = summary.get("confirmation_count", 0)
    batch.error_count = summary.get("error_count", 0)
    batch.warning_count = summary.get("warning_count", 0)


def _save_issues(db: DBSession, batch_id: int, issues: list[dict]) -> None:
    for iss in issues:
        db_issue = RosterImportIssue(
            batch_id=batch_id,
            row_id=iss.get("row_id"),
            employee_id=iss.get("employee_id"),
            field_key=iss.get("field_key"),
            issue_code=iss.get("issue_code", ""),
            severity=iss.get("severity", IssueSeverity.WARNING.value),
            title=iss.get("title", ""),
            message=iss.get("message"),
            old_value_json=(
                json.dumps(iss.get("old_value"), ensure_ascii=False, default=str)
                if iss.get("old_value") is not None else None
            ),
            new_value_json=(
                json.dumps(iss.get("new_value"), ensure_ascii=False, default=str)
                if iss.get("new_value") is not None else None
            ),
            allowed_actions_json=json.dumps(
                iss.get("allowed_actions", []), ensure_ascii=False
            ),
            resolution_status=ResolutionStatus.PENDING,
        )
        db.add(db_issue)


def _get_current_mappings(batch: RosterImportBatch) -> dict[str, str]:
    try:
        # 优先使用 column_mappings_json，兼容旧 header_row
        if hasattr(batch, "column_mappings_json") and batch.column_mappings_json:
            data = json.loads(batch.column_mappings_json)
        else:
            data = json.loads(batch.header_row or "[]")
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, list):
        return {}

    mappings: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        header = item.get("header")
        field_key = item.get("field_key")
        if header and field_key:
            mappings[str(header)] = str(field_key)
    return mappings


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _is_formal_employment(emp_type: str) -> bool:
    formal_values = {"FORMAL", "正式", "正式员工", "正式工"}
    return emp_type.upper() in {"FORMAL"} or emp_type in formal_values


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _looks_like_parsed_salary(text: str) -> bool:
    if not text:
        return True
    if text.strip().isdigit():
        return True
    import re
    if re.search(r"[\d,.]+", text):
        return True
    return False


def _looks_suspicious_pdp(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return True
    import re
    if re.search(r"https?://", text, re.IGNORECASE):
        return True
    alpha_ratio = sum(1 for c in text if c.isalpha()) / max(len(text), 1)
    if alpha_ratio < 0.3:
        return True
    return False

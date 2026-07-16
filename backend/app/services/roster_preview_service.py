"""花名册导入预览服务。

字段分类全部使用统一策略（roster_field_policy），
不再各自维护字段列表。

生命周期判断全部使用统一评估器（roster_lifecycle_evaluator），
不再在预览和提交中使用不同规则。
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
    ExecutionStatus,
    ImportAction,
    IssueAction,
    IssueSeverity,
    ProbationStatus,
    ResolutionStatus,
    ReviewStatus,
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
from .roster_lifecycle_evaluator import evaluate_roster_lifecycle

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
        region_skip, region_issue = _check_cooperation_region(new_data, row)
        if region_skip:
            cooperation_row_ids.add(row.id)
            row.row_status = RosterRowStatus.SKIPPED
            row.import_action = ImportAction.SKIP
            row.review_status = ReviewStatus.IGNORED
            row.execution_status = ExecutionStatus.SKIPPED
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
        "info_count": 0,
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
                "import_action": ImportAction.SKIP.value,
                "review_status": ReviewStatus.IGNORED.value,
                "execution_status": ExecutionStatus.SKIPPED.value,
                "diff_fields": [],
                "issues": [{
                    "issue_code": "REGION_COOPERATION",
                    "severity": "INFO",
                    "title": "地区为合作，不纳入系统",
                    "message": "该员工所在地区标记为「合作」，跳过导入员工生命周期系统。",
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

        row_status, diff_list, issue_list, import_action_value, review_status_value = _classify_row(
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
        if import_action_value:
            row.import_action = import_action_value
        if review_status_value:
            row.review_status = review_status_value
        row.execution_status = ExecutionStatus.PENDING
        # 使用与 _classify_row 一致的活跃匹配逻辑写入 employee_id
        matched_employee: Employee | None = None
        if matched:
            active_matches = [
                e for e in matched
                if not e.is_deleted and e.employee_status != EmployeeStatus.ENTRY_ERROR.value
            ]
            if len(active_matches) == 1:
                matched_employee = active_matches[0]
                row.employee_id = matched_employee.id
        if diff_list:
            row.diff_json = json.dumps(diff_list, ensure_ascii=False, default=str)

        _accumulate_summary(summary, row_status, issue_list)

        row_preview = {
            "row_no": row.row_no,
            "employee_id": matched_employee.id if matched_employee else None,
            "normalized_name": row.normalized_name,
            "matched_employee_name": matched_employee.name if matched_employee else None,
            "row_status": row_status.value,
            "import_action": import_action_value.value if import_action_value else None,
            "review_status": review_status_value.value if review_status_value else None,
            "execution_status": ExecutionStatus.PENDING.value,
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
            state["actual_regularization_date"] = employment.actual_regularization_date
            state["employment_type"] = _enum_value(employment.employment_type) if employment.employment_type else None
        else:
            for f in ("work_city", "work_mode", "team_name", "hire_date", "employment_status",
                      "probation_months", "regularization_date", "actual_regularization_date", "employment_type"):
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
# 合作地区检查
# ============================================================


def _check_cooperation_region(
    new_data: dict, row: RosterImportRow
) -> tuple[bool, dict | None]:
    """检查是否合作地区，返回 (is_skip, issue)。"""
    if is_cooperation_region(new_data):
        return True, {
            "issue_code": "REGION_COOPERATION",
            "severity": IssueSeverity.INFO.value,
            "title": "地区为合作，不纳入系统",
            "message": "该员工所在地区标记为「合作」，跳过导入员工生命周期系统。",
            "field_key": "work_city",
            "allowed_actions": [],
        }
    return False, None


# ============================================================
# 行分类
# ============================================================


def _classify_row(
    db: DBSession,
    row: RosterImportRow,
    matched_employees: list[Employee],
    all_rows_by_name: dict[str, list[RosterImportRow]],
    current_state: dict[str, Any] | None = None,
) -> tuple[RosterRowStatus, list[dict], list[dict], ImportAction | None, ReviewStatus | None]:
    """对单行数据进行分类。

    Returns:
        (row_status, diff_list, issue_list, import_action, review_status)
    """
    name = row.normalized_name
    issues: list[dict] = []
    new_data = _parse_row_data(row)

    # ── 姓名检查（BLOCKER）──
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
        return (RosterRowStatus.ERROR, [], issues, ImportAction.NEW, ReviewStatus.ERROR)

    # ── Excel 内重复姓名 ──
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
        return (RosterRowStatus.ERROR, [], issues, ImportAction.NEW, ReviewStatus.ERROR)

    # ── 筛选活跃匹配结果 ──
    active_matched = [
        e for e in matched_employees
        if not e.is_deleted and e.employee_status != EmployeeStatus.ENTRY_ERROR.value
    ]

    # ── 多条匹配 ──
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
        return (RosterRowStatus.ERROR, [], issues, ImportAction.NEW, ReviewStatus.ERROR)

    # ── 无匹配 = NEW 行 ──
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
            return (RosterRowStatus.ERROR, [], issues, ImportAction.NEW, ReviewStatus.ERROR)

        # NEW 行：执行完整生命周期评估和所有数据质量检查
        lifecycle_result = evaluate_roster_lifecycle(new_data)
        lc_issues = lifecycle_result.get("issues", [])

        # 合并生命周期问题的严重级别到 issues
        for lc_issue in lc_issues:
            sev = IssueSeverity(lc_issue.get("severity", IssueSeverity.WARNING.value))
            issues.append(
                _build_issue(
                    issue_code=lc_issue.get("issue_code", "UNKNOWN"),
                    severity=sev,
                    title=lc_issue.get("title", ""),
                    message=lc_issue.get("message"),
                    field_key=lc_issue.get("field_key"),
                    old_value=lc_issue.get("old_value"),
                    new_value=lc_issue.get("new_value"),
                    allowed_actions=lc_issue.get("allowed_actions", []),
                )
            )

        # 保存生命周期决策到行
        row.lifecycle_decision_json = json.dumps(lifecycle_result, ensure_ascii=False, default=str)

        # 薪酬文本解析警告
        _add_salary_issues(new_data, issues)
        # PDP 可疑内容检查
        _add_pdp_issues(new_data, issues)

        # 决定审核状态
        has_blocker = any(
            iss.get("severity") == IssueSeverity.BLOCKER.value for iss in issues
        )
        has_warning = any(
            iss.get("severity") == IssueSeverity.WARNING.value for iss in issues
        )

        if has_blocker:
            return (RosterRowStatus.ERROR, [], issues, ImportAction.NEW, ReviewStatus.ERROR)
        if has_warning:
            return (RosterRowStatus.NEEDS_CONFIRMATION, [], issues, ImportAction.NEW, ReviewStatus.NEEDS_CONFIRMATION)

        return (RosterRowStatus.NEW, [], issues, ImportAction.NEW, ReviewStatus.CLEAN)

    # ── 精确匹配到一个 = UPDATE/UNCHANGED ──
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

    diff_list = _compute_diff(current_state, new_data)

    # 更新行也执行生命周期评估
    lifecycle_result = evaluate_roster_lifecycle(new_data)
    lc_issues = lifecycle_result.get("issues", [])
    for lc_issue in lc_issues:
        sev = IssueSeverity(lc_issue.get("severity", IssueSeverity.WARNING.value))
        issues.append(
            _build_issue(
                issue_code=lc_issue.get("issue_code", "UNKNOWN"),
                severity=sev,
                title=lc_issue.get("title", ""),
                message=lc_issue.get("message"),
                field_key=lc_issue.get("field_key"),
                old_value=lc_issue.get("old_value"),
                new_value=lc_issue.get("new_value"),
                allowed_actions=lc_issue.get("allowed_actions", []),
            )
        )

    # 保存生命周期决策
    row.lifecycle_decision_json = json.dumps(lifecycle_result, ensure_ascii=False, default=str)

    # 额外问题生成
    extra_issues = _generate_issues(
        row, matched_employees, None, diff_list, all_rows_by_name, new_data, current_state
    )
    issues.extend(extra_issues)

    # 决定最终状态
    if not diff_list:
        status = RosterRowStatus.UNCHANGED
        import_action = ImportAction.UNCHANGED
        review_status = ReviewStatus.CLEAN
    else:
        has_confirmation = any(
            d.get("change_type") == "NEEDS_CONFIRMATION" for d in diff_list
        )
        has_update = any(
            d.get("change_type") == "UPDATE" for d in diff_list
        )
        has_blocker = any(
            iss.get("severity") == IssueSeverity.BLOCKER.value for iss in issues
        )
        has_warning = any(
            iss.get("severity") == IssueSeverity.WARNING.value for iss in issues
        )

        if has_blocker:
            status = RosterRowStatus.ERROR
            import_action = ImportAction.UPDATE
            review_status = ReviewStatus.ERROR
        elif has_confirmation or has_warning:
            status = RosterRowStatus.NEEDS_CONFIRMATION
            import_action = ImportAction.UPDATE
            review_status = ReviewStatus.NEEDS_CONFIRMATION
        elif has_update:
            status = RosterRowStatus.UPDATE
            import_action = ImportAction.UPDATE
            review_status = ReviewStatus.CLEAN
        else:
            status = RosterRowStatus.UNCHANGED
            import_action = ImportAction.UNCHANGED
            review_status = ReviewStatus.CLEAN

    return (status, diff_list, issues, import_action, review_status)


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


def _add_salary_issues(data: dict, issues: list[dict]) -> None:
    """薪资文本解析问题。"""
    salary_text = data.get("raw_salary_text")
    if salary_text and isinstance(salary_text, str) and salary_text.strip():
        if not _looks_like_parsed_salary(salary_text):
            issues.append(
                _build_issue(
                    issue_code="SALARY_UNPARSABLE",
                    severity=IssueSeverity.WARNING,
                    title="薪酬文本可能无法自动解析",
                    message=f"薪酬文本「{salary_text[:100]}」格式不标准，系统可能无法完全自动解析。",
                    field_key="raw_salary_text",
                    new_value=salary_text[:200],
                    allowed_actions=[IssueAction.IGNORE.value, IssueAction.MODIFY_VALUE.value],
                )
            )


def _add_pdp_issues(data: dict, issues: list[dict]) -> None:
    """PDP 测评内容检查。"""
    pdp_text = data.get("pdp_result") or data.get("assessment_result")
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


def _generate_issues(
    row: RosterImportRow,
    matched_employees: list[Employee],
    row_status: RosterRowStatus | None,
    diff: list[dict],
    all_rows_by_name: dict[str, list[RosterImportRow]],
    new_data: dict[str, Any] | None = None,
    current_state: dict[str, Any] | None = None,
) -> list[dict]:
    """根据行数据、匹配结果和差异生成额外问题。

    此函数只在有匹配员工的 Update 行调用。
    NEW 行的所有问题已在中生命周期评估器 + _add_salary_issues + _add_pdp_issues 生成。
    """
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

    # ── 薪酬文本解析警告（WARNING）──
    _add_salary_issues(new_data, issues)

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
                allowed_actions=["IGNORE", "MODIFY_VALUE"],
            )
        )

    # ── PDP 测评内容可疑（WARNING）──
    _add_pdp_issues(new_data, issues)

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
        elif sev == IssueSeverity.INFO.value:
            summary["info_count"] = summary.get("info_count", 0) + 1


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

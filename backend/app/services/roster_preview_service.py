"""花名册导入预览服务。"""

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
try:
    from .roster_mapping_service import resolve_value_alias
except ImportError:
    # roster_mapping_service 尚未创建，resolve_value_alias 将在需要时延迟解析
    resolve_value_alias = None  # type: ignore[assignment]

# ============================================================
# 字段分类
# ============================================================

# 自动更新字段：Excel 值直接覆盖系统值，无需人工逐项确认
AUTO_UPDATE_FIELDS = [
    "mobile",
    "email",
    "residence_address",
    "education_level",
    "graduation_school",
    "major",
    "household_registration",
    "household_type",
    "social_insurance_status",
    "housing_fund_status",
    "social_insurance_policy",
    "housing_fund_policy",
    "social_insurance_start_date",
    "housing_fund_start_date",
    "benefit_raw_text",
    "work_city",
    "work_mode",
    "team_name",
]

# 确认字段：需要 HR 逐项确认后才应用，不允许静默覆盖
CONFIRMATION_FIELDS = [
    "identity_card",
    "birth_date",
    "gender",
    "contract_status",
    "signing_company",
    "contract_type",
    "bank_card",
    "alipay",
]

# ============================================================
# 标签映射（展示用）
# ============================================================

_FIELD_LABELS: dict[str, str] = {
    "mobile": "手机号",
    "email": "邮箱",
    "residence_address": "居住地址",
    "education_level": "学历",
    "graduation_school": "毕业学校",
    "major": "专业",
    "household_registration": "户籍地址",
    "household_type": "户籍类型",
    "social_insurance_status": "社保状态",
    "housing_fund_status": "公积金状态",
    "social_insurance_policy": "社保缴纳规则",
    "housing_fund_policy": "公积金缴纳规则",
    "social_insurance_start_date": "社保开始日期",
    "housing_fund_start_date": "公积金开始日期",
    "benefit_raw_text": "五险一金原文",
    "work_city": "工作城市",
    "work_mode": "工作模式",
    "team_name": "团队",
    "identity_card": "身份证号",
    "birth_date": "出生日期",
    "gender": "性别",
    "contract_status": "合同状态",
    "signing_company": "签约公司",
    "contract_type": "合同类型",
    "bank_card": "银行卡号",
    "alipay": "支付宝账号",
    "name": "姓名",
    "hire_date": "入职日期",
    "probation_months": "试用期月数",
    "regularization_date": "转正日期",
    "employment_type": "用工类型",
    "raw_salary_text": "薪酬文本",
    "assessment_result": "测评结果",
}

_ACTION_LABELS: dict[RosterRowStatus, list[str]] = {
    RosterRowStatus.NEW: ["import", "skip"],
    RosterRowStatus.UPDATE: ["apply", "skip"],
    RosterRowStatus.UNCHANGED: ["skip"],
    RosterRowStatus.NEEDS_CONFIRMATION: ["confirm", "skip"],
    RosterRowStatus.ERROR: ["skip", "force_import"],
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

    处理步骤：
      1. 加载批次并校验状态（只允许 UPLOADED / MAPPING_REQUIRED / PREVIEW_READY）。
      2. 加载所有行并批量查询员工匹配。
      3. 逐行分类（NEW / UPDATE / UNCHANGED / NEEDS_CONFIRMATION / ERROR）并生成问题。
      4. 更新批次状态为 PREVIEW_READY，持久化问题记录。
      5. 返回含 summary / rows / issues / current_mappings 的 dict。

    参数：
      db: 数据库会话。
      batch_id: 导入批次 ID。

    返回：
      {
        "summary": {"new_count": int, "update_count": int, ...},
        "rows": [RowPreviewItem, ...],
        "issues": [IssueItem, ...],
        "current_mappings": {str: str},
      }
    """
    # 1. 加载批次
    batch = _load_batch(db, batch_id)

    # 2. 加载所有行
    rows = _load_rows(db, batch_id)
    if not rows:
        raise ValueError("批次中没有数据行，无法预览")

    # 3. 收集所有标准化姓名并批量匹配
    all_names = sorted({row.normalized_name for row in rows if row.normalized_name})
    employee_map = _match_employees_batch(db, all_names) if all_names else {}

    # 4. 构建姓名 -> 行列表（用于检测 Excel 内重复）
    all_rows_by_name: dict[str, list[RosterImportRow]] = {}
    for row in rows:
        n = row.normalized_name or ""
        all_rows_by_name.setdefault(n, []).append(row)

    # 5. 逐行处理
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
        matched = employee_map.get(row.normalized_name, [])

        row_status, diff_list, issue_list = _classify_row(
            db,
            row,
            matched,
            all_rows_by_name,
        )

        # 为 issue 绑定 row_id
        for iss in issue_list:
            iss["row_id"] = row.id
            if matched and len(matched) == 1:
                iss.setdefault("employee_id", matched[0].id)

        # 更新行
        row.row_status = row_status
        if diff_list:
            row.diff_json = json.dumps(diff_list, ensure_ascii=False, default=str)

        # 统计
        _accumulate_summary(summary, row_status, issue_list)

        # 构建预览条目
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

    # 6. 更新批次
    _update_batch_summary(batch, summary)
    batch.batch_status = (
        RosterBatchStatus.WAITING_RESOLUTION
        if summary.get("blocker_count", 0) > 0
        else RosterBatchStatus.READY
    )
    db.flush()

    # 7. 持久化问题记录
    _save_issues(db, batch_id, all_issues)
    db.flush()

    # 8. 获取当前映射
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
    """更新批次状态。"""
    batch = _load_batch(db, batch_id)
    batch.batch_status = status
    db.flush()


# ============================================================
# 员工批量匹配
# ============================================================


def _match_employees_batch(
    db: DBSession, names: list[str]
) -> dict[str, list[Employee]]:
    """批量查询员工，返回 ``normalized_name -> [Employee, ...]`` 的映射。

    只返回未逻辑删除且非 ``ENTRY_ERROR`` 状态的活跃员工记录。
    """
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
) -> tuple[RosterRowStatus, list[dict], list[dict]]:
    """对单行数据进行分类。

    返回 ``(row_status, diff_list, issue_list)``。

    分类规则：
      - 姓名为空 → ERROR
      - Excel 内重复姓名 → ERROR
      - 数据库匹配到多条 → ERROR
      - 数据库未匹配到 → NEW
      - 数据库精确匹配一条：
        - 员工已删除 / ENTRY_ERROR → ERROR
        - 员工已离职 → 检查重聘场景
        - 计算差异，根据差异类型决定 UPDATE / UNCHANGED / NEEDS_CONFIRMATION
    """
    name = row.normalized_name
    issues: list[dict] = []

    # ── 姓名为空 ──────────────────────────────────────────
    if not name:
        issues.append(
            _build_issue(
                issue_code="NAME_EMPTY",
                severity=IssueSeverity.BLOCKER,
                title="姓名为空",
                message="该行姓名字段为空，无法匹配员工。请手动补全姓名或跳过该行。",
                field_key="name",
                allowed_actions=["skip", "manual_input"],
            )
        )
        return (RosterRowStatus.ERROR, [], issues)

    # ── Excel 内重复姓名 ──────────────────────────────────
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
                allowed_actions=["skip", "force_new"],
            )
        )
        return (RosterRowStatus.ERROR, [], issues)

    # ── 筛选出活跃匹配结果 ──────────────────────────────
    active_matched = [
        e
        for e in matched_employees
        if not e.is_deleted and e.employee_status != EmployeeStatus.ENTRY_ERROR.value
    ]

    # 多条匹配 → ERROR
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
                allowed_actions=["skip", "manual_select"],
            )
        )
        return (RosterRowStatus.ERROR, [], issues)

    # 无匹配 → NEW
    if len(active_matched) == 0:
        # 检查是否因已删除/ENTRY_ERROR 被过滤
        inactive = [
            e
            for e in matched_employees
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
                    allowed_actions=["skip", "reactivate"],
                )
            )
            return (RosterRowStatus.ERROR, [], issues)
        # ── NEW 行必填字段校验 ─────────────────────────────
        # hire_date 是创建新员工的必需字段，缺失时标记为 ERROR
        _NEW_REQUIRED_FIELDS = ["hire_date"]
        _new_row_data = _parse_row_data(row)
        for _rfield in _NEW_REQUIRED_FIELDS:
            _rval = _new_row_data.get(_rfield)
            if _rval is None or (isinstance(_rval, str) and not _rval.strip()):
                issues.append(
                    _build_issue(
                        issue_code="MISSING_REQUIRED_FIELD",
                        severity=IssueSeverity.BLOCKER,
                        title="缺少必填字段",
                        message=f"必填字段「{_FIELD_LABELS.get(_rfield, _rfield)}」为空，请补充。",
                        field_key=_rfield,
                        allowed_actions=["skip", "add_manually"],
                    )
                )
                return (RosterRowStatus.ERROR, [], issues)
        return (RosterRowStatus.NEW, [], issues)

    # ── 精确匹配到一个 ──────────────────────────────────
    employee = active_matched[0]

    # 已离职 → 重聘场景
    current_employment = _find_current_employment(db, employee.id)
    lifecycle_stage = (
        resolve_lifecycle_stage(current_employment) if current_employment else "UNKNOWN"
    )
    if current_employment and current_employment.employment_status == EmploymentStatus.SEPARATED:
        issues.append(
            _build_issue(
                issue_code="REHIRE_SCENARIO",
                severity=IssueSeverity.WARNING,
                title="已离职员工重新入职",
                message=f"员工「{employee.name}」当前任职状态为「已离职」，"
                f"导入将触发重新入职流程，会创建新的任职记录。",
                field_key=None,
                allowed_actions=["proceed", "skip"],
            )
        )

    # 获取系统当前状态
    current_state = _get_current_state(db, employee)

    # 解析行数据
    new_data = _parse_row_data(row)

    # 计算差异
    diff_list = _compute_diff(current_state, new_data)

    # 生成其他问题
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
        if has_confirmation and has_update:
            status = RosterRowStatus.NEEDS_CONFIRMATION
        elif has_confirmation:
            status = RosterRowStatus.NEEDS_CONFIRMATION
        else:
            status = RosterRowStatus.UPDATE

    return (status, diff_list, issues)


# ============================================================
# 当前状态查询
# ============================================================


def _get_current_state(db: DBSession, employee: Employee) -> dict:
    """获取员工当前系统状态，以扁平 dict 返回。

    聚合 Employee / EmployeeProfile / EmploymentRecord /
    EmploymentContract / EmployeeFinancialAccount 的信息。
    """
    state: dict[str, Any] = {}

    # ── Employee ─────────────────────────────────────────
    state["name"] = employee.name
    state["normalized_name"] = employee.normalized_name
    state["mobile"] = employee.mobile
    state["email"] = employee.email
    state["employee_no"] = employee.employee_no

    # ── EmployeeProfile ─────────────────────────────────
    profile = (
        db.query(EmployeeProfile)
        .filter(
            EmployeeProfile.employee_id == employee.id,
            EmployeeProfile.is_deleted == False,
        )
        .first()
    )
    _PROFILE_FIELDS = [
        "identity_card",
        "gender",
        "birth_date",
        "household_registration",
        "residence_address",
        "household_type",
        "graduation_school",
        "major",
        "education_level",
        "social_insurance_status",
        "housing_fund_status",
        "social_insurance_policy",
        "housing_fund_policy",
        "social_insurance_start_date",
        "housing_fund_start_date",
        "benefit_raw_text",
    ]
    if profile:
        for field in _PROFILE_FIELDS:
            state[field] = getattr(profile, field, None)
    else:
        for field in _PROFILE_FIELDS:
            state[field] = None

    # ── EmploymentRecord ────────────────────────────────
    employment = _find_current_employment(db, employee.id)
    _EMPLOYMENT_FIELDS = [
        "work_city",
        "work_mode",
        "team_name",
        "hire_date",
        "employment_status",
        "probation_months",
        "regularization_date",
        "employment_type",
    ]
    if employment:
        state["work_city"] = employment.work_city
        state["work_mode"] = (
            _enum_value(employment.work_mode) if employment.work_mode else None
        )
        state["team_name"] = employment.team_name
        state["hire_date"] = employment.hire_date
        state["employment_status"] = (
            _enum_value(employment.employment_status) if employment.employment_status else None
        )
        state["probation_months"] = employment.probation_months
        state["regularization_date"] = employment.regularization_date
        state["employment_type"] = (
            _enum_value(employment.employment_type) if employment.employment_type else None
        )
    else:
        for field in _EMPLOYMENT_FIELDS:
            state[field] = None

    # ── EmploymentContract（最近一条）───────────────────
    contract = (
        db.query(EmploymentContract)
        .filter(
            EmploymentContract.employee_id == employee.id,
            EmploymentContract.is_deleted == False,
        )
        .order_by(EmploymentContract.id.desc())
        .first()
    )
    if contract:
        state["contract_status"] = contract.contract_status
        state["signing_company"] = contract.signing_company
        state["contract_type"] = (
            _enum_value(contract.contract_type) if contract.contract_type else None
        )
    else:
        state["contract_status"] = None
        state["signing_company"] = None
        state["contract_type"] = None

    # ── EmployeeFinancialAccount ────────────────────────
    # 银行卡
    bank = (
        db.query(EmployeeFinancialAccount)
        .filter(
            EmployeeFinancialAccount.employee_id == employee.id,
            EmployeeFinancialAccount.account_type == AccountType.BANK,
            EmployeeFinancialAccount.account_status == AccountStatus.ACTIVE,
            EmployeeFinancialAccount.is_deleted == False,
        )
        .order_by(
            EmployeeFinancialAccount.is_primary.desc(),
            EmployeeFinancialAccount.id.desc(),
        )
        .first()
    )
    state["bank_card"] = bank.account_no if bank else None

    # 支付宝
    alipay = (
        db.query(EmployeeFinancialAccount)
        .filter(
            EmployeeFinancialAccount.employee_id == employee.id,
            EmployeeFinancialAccount.account_type == AccountType.ALIPAY,
            EmployeeFinancialAccount.account_status == AccountStatus.ACTIVE,
            EmployeeFinancialAccount.is_deleted == False,
        )
        .order_by(
            EmployeeFinancialAccount.is_primary.desc(),
            EmployeeFinancialAccount.id.desc(),
        )
        .first()
    )
    state["alipay"] = alipay.account_no if alipay else None

    return state


def _find_current_employment(db: DBSession, employee_id: int) -> EmploymentRecord | None:
    """找到员工的当前有效任职（按任职序号倒序）。"""
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
    """计算当前值与新值的差异。

    规则：
      - **空 Excel 值不覆盖系统已有值** —— 如果新值为 ``None`` 或空白字符串，
        即使系统已有值也不会标记为差异。
      - ``AUTO_UPDATE_FIELDS`` 的差异标记为 ``UPDATE``。
      - ``CONFIRMATION_FIELDS`` 的差异标记为 ``NEEDS_CONFIRMATION``。

    返回差异列表，每个元素：:
      {
        "field_key": str,
        "field_label": str,
        "old_value": str | None,
        "new_value": str | None,
        "change_type": "UPDATE" | "NEEDS_CONFIRMATION",
      }
    """
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
    """如果字段值发生了变化，追加一条差异记录。

    新值为 None 或空白时不视为变更（不覆盖系统已有值）。
    """
    old_val = current.get(field)
    new_val = new.get(field)

    # 空值不覆盖
    if new_val is None and not (
        field in _BENEFIT_CLEARABLE_FIELDS
        and new.get("benefit_parse_status") == "PARSED"
        and field in new
    ):
        return
    if isinstance(new_val, str) and not new_val.strip():
        return

    # 相等则不记录
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
    """比较两个值是否在语义上相等，处理日期和 None 等类型。"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return _serialize_value(a) == _serialize_value(b)


def _serialize_value(value: Any) -> str | None:
    """将值序列化为规范字符串用于比较和展示。"""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).strip()
    return s if s else None


def _parse_row_data(row: RosterImportRow) -> dict:
    """解析行的归一化数据 JSON 为 dict。

    返回空 dict 表示没有可解析的数据。
    """
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
    """根据行数据、匹配结果和差异生成额外问题。

    参数 ``new_data`` 和 ``current_state`` 提供额外的上下文以便执行
    更细致的数据校验；如果未传入，函数内部会尝试重新解析。

    返回 issues list。
    """
    issues: list[dict] = []
    name = row.normalized_name

    if new_data is None:
        new_data = _parse_row_data(row)

    employee = matched_employees[0] if len(matched_employees) == 1 else None

    if current_state is None:
        current_state = {}

    # ── 姓名规范校验（BLOCKER）────────────────────────────
    if not name:
        issues.append(
            _build_issue(
                issue_code="NAME_EMPTY",
                severity=IssueSeverity.BLOCKER,
                title="姓名为空",
                message="姓名字段为空，无法完成匹配。",
                field_key="name",
                allowed_actions=["skip", "manual_input"],
            )
        )

    # ── 试用期月份数（BLOCKER）────────────────────────────
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
                        message=f"试用期月数必须为正整数，当前值：{pm}。",
                        field_key="probation_months",
                        old_value=current_state.get("probation_months"),
                        new_value=str(pm),
                        allowed_actions=["correct_manually", "ignore"],
                    )
                )
            elif pm > 12:
                issues.append(
                    _build_issue(
                        issue_code="INVALID_PROBATION_MONTHS",
                        severity=IssueSeverity.WARNING,
                        title="试用期月份数偏长",
                        message=f"试用期 {pm} 个月超过常见范围（1-12 个月），请确认。",
                        field_key="probation_months",
                        old_value=current_state.get("probation_months"),
                        new_value=str(pm),
                        allowed_actions=["correct_manually", "ignore"],
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
                    allowed_actions=["correct_manually", "ignore"],
                )
            )

    # ── 必填字段校验（BLOCKER）────────────────────────────
    # 这些字段在行数据中应为非空；name 和 hire_date 是最基本的必填项
    _REQUIRED_FIELDS = ["hire_date"]
    for rfield in _REQUIRED_FIELDS:
        rval = new_data.get(rfield)
        if rval is None or (isinstance(rval, str) and not rval.strip()):
            issues.append(
                _build_issue(
                    issue_code="MISSING_REQUIRED_FIELD",
                    severity=IssueSeverity.BLOCKER,
                    title=f"缺少必填字段",
                    message=f"必填字段「{_FIELD_LABELS.get(rfield, rfield)}」为空，请补充。",
                    field_key=rfield,
                    allowed_actions=["skip", "add_manually"],
                )
            )

    # ── 转正日期缺失提醒（WARNING）────────────────────────
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
                    allowed_actions=["add_manually", "ignore"],
                )
            )

    # ── 年龄与出生日期交叉校验（WARNING）──────────────────
    birth_date_raw = new_data.get("birth_date") or current_state.get("birth_date")
    age_raw = new_data.get("age")
    if birth_date_raw and age_raw is not None:
        try:
            bd = _parse_date(birth_date_raw)
            declared_age = int(age_raw)
            if bd is not None:
                today = date.today()
                computed_age = (
                    today.year
                    - bd.year
                    - ((today.month, today.day) < (bd.month, bd.day))
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
                            allowed_actions=["correct_manually", "ignore"],
                        )
                    )
        except (ValueError, TypeError):
            pass

    # ── 工龄校验（WARNING）────────────────────────────────
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
                            allowed_actions=["correct_manually", "ignore"],
                        )
                    )
        except (ValueError, TypeError):
            pass

    # ── 薪酬文本解析警告（WARNING）────────────────────────
    salary_text = new_data.get("raw_salary_text")
    if salary_text and isinstance(salary_text, str) and salary_text.strip():
        if not _looks_like_parsed_salary(salary_text):
            issues.append(
                _build_issue(
                    issue_code="SALARY_UNPARSABLE",
                    severity=IssueSeverity.WARNING,
                    title="薪酬文本可能无法自动解析",
                    message=f"薪酬文本「{salary_text[:100]}」格式不标准，"
                    f"系统可能无法完全自动解析。导入后请手工核对薪酬数据。",
                    field_key="raw_salary_text",
                    new_value=salary_text[:200],
                    allowed_actions=["ignore", "correct_manually"],
                )
            )

    benefit_parse_status = new_data.get("benefit_parse_status")
    if benefit_parse_status == "UNRECOGNIZED":
        issues.append(
            _build_issue(
                issue_code="BENEFIT_TEXT_UNRECOGNIZED",
                severity=IssueSeverity.WARNING,
                title="五险一金缴纳方案无法识别",
                message="五险一金原文无法自动解析，系统只保留原文，不自动修改社保或公积金方案。",
                field_key="benefit_raw_text",
                old_value=current_state.get("benefit_raw_text"),
                new_value=new_data.get("benefit_raw_text"),
                allowed_actions=["correct_manually", "ignore"],
            )
        )

    # ── PDP 测评内容可疑（WARNING）────────────────────────
    pdp_text = new_data.get("pdp_result") or new_data.get("assessment_result")
    if pdp_text and isinstance(pdp_text, str) and pdp_text.strip():
        if _looks_suspicious_pdp(pdp_text):
            issues.append(
                _build_issue(
                    issue_code="PDP_CONTENT_SUSPICIOUS",
                    severity=IssueSeverity.WARNING,
                    title="PDP 测评内容疑似异常",
                    message=f"PDP 测评文本「{pdp_text[:100]}」看起来不符合预期的测评报告格式。"
                    f"请核实后手动上传或修正。",
                    field_key="pdp_result",
                    new_value=pdp_text[:200],
                    allowed_actions=["ignore", "correct_manually"],
                )
            )

    # ── 纯图文预警（WARNING）──────────────────────────────
    image_text = new_data.get("image_text") or new_data.get("attachment_description")
    if image_text and isinstance(image_text, str) and image_text.strip():
        issues.append(
            _build_issue(
                issue_code="IMAGE_TEXT_ONLY",
                severity=IssueSeverity.WARNING,
                title="附件说明为纯文本",
                message="该字段仅包含文本描述，可能需要上传附件以替代或补充。",
                field_key="image_text",
                new_value=image_text[:200],
                allowed_actions=["ignore", "upload_attachment"],
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
    """构建 Issue dict 的内部方法。"""
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
    """将内部 issue dict 转为前端展示格式。"""
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
    """加载批次，校验存在性和可预览状态。"""
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
    """加载批次的所有数据行。"""
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
    """累加汇总计数。"""
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
    """将汇总结果写回 batch 记录。"""
    batch.total_rows = summary.get("total_rows", 0)
    batch.new_count = summary.get("new_count", 0)
    batch.update_count = summary.get("update_count", 0)
    batch.unchanged_count = summary.get("unchanged_count", 0)
    batch.confirmation_count = summary.get("confirmation_count", 0)
    batch.error_count = summary.get("error_count", 0)
    # warning_count 共享自 summary 中的 warning_count 字段
    batch.warning_count = summary.get("warning_count", 0)


def _save_issues(db: DBSession, batch_id: int, issues: list[dict]) -> None:
    """将问题列表持久化到 ``roster_import_issue`` 表。"""
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
                if iss.get("old_value") is not None
                else None
            ),
            new_value_json=(
                json.dumps(iss.get("new_value"), ensure_ascii=False, default=str)
                if iss.get("new_value") is not None
                else None
            ),
            allowed_actions_json=json.dumps(
                iss.get("allowed_actions", []), ensure_ascii=False
            ),
            resolution_status=ResolutionStatus.PENDING,
        )
        db.add(db_issue)


def _get_current_mappings(batch: RosterImportBatch) -> dict[str, str]:
    """从批次中获取当前字段映射配置。"""
    try:
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
    """判断用工类型是否为正式。"""
    formal_values = {"FORMAL", "正式", "正式员工", "正式工"}
    return emp_type.upper() in {"FORMAL"} or emp_type in formal_values


def _parse_date(value: Any) -> date | None:
    """尝试将值解析为 ``date`` 对象。"""
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
    """粗略判断薪酬文本是否为可解析格式。

    如果文本中包含数字和常见单位（元/千/万）或匹配
    「数字+单位」模式则认为可解析。
    """
    if not text:
        return True
    # 纯数字 → 可解析
    if text.strip().isdigit():
        return True
    # 包含常见分隔符和数字 → 可解析
    import re

    if re.search(r"[\d,.]+", text):
        return True
    return False


def _looks_suspicious_pdp(text: str) -> bool:
    """粗略判断 PDP 测评文本是否疑似异常。

    如果文本过短、包含大量标点符号或 URL，视为可疑。
    """
    if not text or len(text.strip()) < 10:
        return True
    import re

    # 包含 URL
    if re.search(r"https?://", text, re.IGNORECASE):
        return True
    # 全是标点符号或非文字内容
    alpha_ratio = sum(1 for c in text if c.isalpha()) / max(len(text), 1)
    if alpha_ratio < 0.3:
        return True
    return False

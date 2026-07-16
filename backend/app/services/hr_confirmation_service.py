"""HR 待确认事项服务。

核心原则：
1. 所有 issue_code 使用 ConfirmationIssueCode 枚举，禁止直接写字符串。
2. 使用处理器注册表（CONFIRMATION_HANDLERS）代替 if/elif 链。
3. 未知 issue_code 必须报错，确认事项保持 PENDING。
4. 只有业务操作成功，才能把事项改成 CONFIRMED。
5. 业务操作失败时必须回滚，事项仍为 PENDING。
6. 银行卡/支付宝确认需要幂等。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    AccountStatus,
    ConfirmationIssueCode,
    ConfirmationItemStatus,
    EmploymentStatus,
    OperationObjectType,
    ProbationStatus,
)
from ..exceptions import (
    InvalidStateTransition,
    ResourceNotFound,
    ValidationError,
)
from ..models import (
    Employee,
    EmployeeFinancialAccount,
    EmployeeProfile,
    EmploymentContract,
    EmploymentRecord,
    HrConfirmationItem,
    SeparationRecord,
)
from ..models.note import EmployeeNote
from .date_utils import parse_date_value as _parse_date
from .operation_log_service import create_log


# ============================================================
# 处理器注册表
# ============================================================

# 处理器签名: (db, item, before_data, after_data, operator_id, now) -> None
# 处理成功时不返回特殊值；失败时抛出异常。
ConfirmationHandler = Callable[
    [DBSession, HrConfirmationItem, Any, Any, str, datetime],
    None,
]

_CONFIRMATION_HANDLERS: dict[str, ConfirmationHandler] = {}


def _register(issue_code: ConfirmationIssueCode) -> Callable[[ConfirmationHandler], ConfirmationHandler]:
    """注册一个确认事项处理器。"""
    def decorator(handler: ConfirmationHandler) -> ConfirmationHandler:
        _CONFIRMATION_HANDLERS[issue_code.value] = handler
        return handler
    return decorator


def get_handler(issue_code: str) -> ConfirmationHandler | None:
    """获取对应 issue_code 的处理器。"""
    return _CONFIRMATION_HANDLERS.get(issue_code)


# ============================================================
# 处理器实现
# ============================================================


@_register(ConfirmationIssueCode.IDENTITY_CARD_CHANGE)
def _handle_identity_card_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理身份证号变更。"""
    if not after_data:
        return
    new_value = after_data.get("identity_card")
    if new_value is None:
        return
    _update_profile_field(db, item.employee_id, "identity_card", new_value, operator_id, now)


@_register(ConfirmationIssueCode.BIRTH_DATE_CHANGE)
def _handle_birth_date_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理出生日期变更。"""
    if not after_data:
        return
    new_value = after_data.get("birth_date")
    if new_value is None:
        return
    _update_profile_field(db, item.employee_id, "birth_date", new_value, operator_id, now)


@_register(ConfirmationIssueCode.GENDER_CHANGE)
def _handle_gender_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理性别变更。"""
    if not after_data:
        return
    new_value = after_data.get("gender")
    if new_value is None:
        return
    _update_profile_field(db, item.employee_id, "gender", new_value, operator_id, now)


@_register(ConfirmationIssueCode.NAME_CHANGE)
def _handle_name_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理姓名变更。"""
    employee = db.query(Employee).filter(Employee.id == item.employee_id).first()
    if employee and after_data:
        new_name = after_data.get("name")
        if new_name:
            employee.name = new_name
            employee.updated_by = operator_id
            db.flush()


@_register(ConfirmationIssueCode.CONTRACT_CHANGE)
def _handle_contract_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理合同变更：创建新合同记录。"""
    if not after_data:
        return

    contract = EmploymentContract(
        employee_id=item.employee_id,
        employment_id=item.employment_id,
        contract_status=after_data.get("contract_status"),
        signing_company=after_data.get("signing_company"),
        contract_type=after_data.get("contract_type"),
        start_date=_parse_date(after_data.get("start_date")),
        end_date=_parse_date(after_data.get("end_date")),
        signing_sequence=after_data.get("signing_sequence"),
        confirmed_at=now,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(contract)
    db.flush()


@_register(ConfirmationIssueCode.CONTRACT_COMPANY_CHANGE)
def _handle_contract_company_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理合同签订公司变更。"""
    _handle_contract_change(db, item, before_data, after_data, operator_id, now)


@_register(ConfirmationIssueCode.CONTRACT_TERM_CHANGE)
def _handle_contract_term_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理合同期限变更。"""
    _handle_contract_change(db, item, before_data, after_data, operator_id, now)


@_register(ConfirmationIssueCode.NEW_BANK_ACCOUNT)
def _handle_new_bank_account(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理新增银行卡。

    幂等规则：
    - employee_id + BANK + account_no 已存在 → 无变化
    - 不存在 → 新增银行卡，旧卡保留
    - 未指定 is_primary → 默认为非工资卡
    """
    if not after_data:
        return

    account_no = after_data.get("account_no")
    if not account_no:
        return

    # 幂等检查
    existing = (
        db.query(EmployeeFinancialAccount)
        .filter(
            EmployeeFinancialAccount.employee_id == item.employee_id,
            EmployeeFinancialAccount.account_type == "BANK",
            EmployeeFinancialAccount.account_no == account_no,
            EmployeeFinancialAccount.is_deleted == False,
        )
        .first()
    )
    if existing:
        # 已存在相同卡号，无变化
        return

    # 检查是否要设为工资卡
    is_primary = after_data.get("is_primary", False)
    if is_primary:
        # 取消旧工资卡的主卡标志
        (
            db.query(EmployeeFinancialAccount)
            .filter(
                EmployeeFinancialAccount.employee_id == item.employee_id,
                EmployeeFinancialAccount.account_type == "BANK",
                EmployeeFinancialAccount.is_primary == True,
                EmployeeFinancialAccount.is_deleted == False,
            )
            .update({"is_primary": False})
        )

    account = EmployeeFinancialAccount(
        employee_id=item.employee_id,
        account_type="BANK",
        account_no=account_no,
        bank_name=after_data.get("bank_name"),
        is_primary=is_primary,
        account_status=AccountStatus.ACTIVE.value,
        confirmed_at=now,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(account)
    db.flush()


@_register(ConfirmationIssueCode.NEW_ALIPAY_ACCOUNT)
def _handle_new_alipay_account(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理新增支付宝账号。

    幂等规则同银行卡。
    """
    if not after_data:
        return

    account_no = after_data.get("account_no")
    if not account_no:
        return

    # 幂等检查
    existing = (
        db.query(EmployeeFinancialAccount)
        .filter(
            EmployeeFinancialAccount.employee_id == item.employee_id,
            EmployeeFinancialAccount.account_type == "ALIPAY",
            EmployeeFinancialAccount.account_no == account_no,
            EmployeeFinancialAccount.is_deleted == False,
        )
        .first()
    )
    if existing:
        return

    account = EmployeeFinancialAccount(
        employee_id=item.employee_id,
        account_type="ALIPAY",
        account_no=account_no,
        bank_name=None,
        is_primary=False,
        account_status=AccountStatus.ACTIVE.value,
        confirmed_at=now,
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(account)
    db.flush()


@_register(ConfirmationIssueCode.ACTUAL_HIRE_DATE_CHANGE)
def _handle_actual_hire_date_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理实际入职日期变更。

    只查找当前有效任职（PENDING / ACTIVE / SEPARATING），
    不修改历史 SEPARATED 记录。
    """
    if not after_data:
        return

    new_hire_date = _parse_date(
        after_data.get("hire_date") or after_data.get("actual_hire_date")
    )
    if not new_hire_date:
        return

    if item.employment_id:
        emp = db.query(EmploymentRecord).filter(
            EmploymentRecord.id == item.employment_id,
            EmploymentRecord.employment_status.in_([
                EmploymentStatus.PENDING,
                EmploymentStatus.ACTIVE,
                EmploymentStatus.SEPARATING,
            ]),
        ).first()
        if emp:
            emp.hire_date = new_hire_date
            emp.actual_hire_date = new_hire_date
            emp.employment_status = EmploymentStatus.ACTIVE.value
            emp.updated_by = operator_id
            db.flush()


@_register(ConfirmationIssueCode.PENDING_SEPARATION)
def _handle_pending_separation(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理待离职确认。"""
    if not after_data:
        return

    planned_date = _parse_date(
        after_data.get("planned_separation_date")
        or after_data.get("separation_date")
    )
    if not planned_date:
        return

    if item.employment_id:
        emp = db.query(EmploymentRecord).filter(
            EmploymentRecord.id == item.employment_id,
            EmploymentRecord.is_deleted == False,
        ).first()
        if emp and emp.employment_status != EmploymentStatus.SEPARATED.value:
            emp.separation_date = planned_date
            if emp.employment_status == EmploymentStatus.ACTIVE.value:
                emp.employment_status = EmploymentStatus.SEPARATING.value
            emp.updated_by = operator_id
            emp.updated_at = now

        record = SeparationRecord(
            employment_id=item.employment_id,
            planned_separation_date=planned_date,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(record)
        db.flush()


@_register(ConfirmationIssueCode.POSSIBLE_REEMPLOYMENT)
def _handle_possible_reemployment(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理再次入职。

    P0 规则：
    - 实际入职日期必须由 HR 填写，不允许为空时默认今天。
    - 创建新的任职记录，不覆盖历史任职。
    - 同一时间只能有一条有效任职。
    - 重新计算试用期。
    - 幂等生成 7天、15天、30天、45天和转正面谈任务。
    """
    if not after_data:
        raise ValidationError("缺少再次入职数据")

    hire_date = _parse_date(
        after_data.get("hire_date") or after_data.get("actual_hire_date")
    )
    if not hire_date:
        raise ValidationError("再次入职必须提供实际入职日期")

    # 不允许晚于今天
    if hire_date > datetime.now().date():
        raise ValidationError("实际入职日期不能晚于今天")

    # 查找当前有效任职（PENDING / ACTIVE / SEPARATING）
    current_employment = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == item.employee_id,
            EmploymentRecord.employment_status.in_([
                EmploymentStatus.PENDING,
                EmploymentStatus.ACTIVE,
                EmploymentStatus.SEPARATING,
            ]),
            EmploymentRecord.is_deleted == False,
        )
        .first()
    )
    if current_employment:
        raise ValidationError(
            f"员工已有有效任职（状态: {current_employment.employment_status.value}），"
            f"不能重新入职"
        )

    # 获取下一个 employment_seq
    last_emp = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == item.employee_id,
            EmploymentRecord.is_deleted == False,
        )
        .order_by(EmploymentRecord.employment_seq.desc())
        .first()
    )
    next_seq = (last_emp.employment_seq + 1) if last_emp else 1

    # 解析试用期信息
    prob_months = after_data.get("probation_months", 3)
    try:
        prob_months = int(prob_months)
    except (ValueError, TypeError):
        prob_months = 3
    if prob_months < 1 or prob_months > 6:
        prob_months = 3

    from ..services.employment_service import calculate_probation_end_date
    probation_end = calculate_probation_end_date(hire_date, prob_months)

    emp = EmploymentRecord(
        employee_id=item.employee_id,
        employment_seq=next_seq,
        employment_status=EmploymentStatus.ACTIVE.value,
        hire_date=hire_date,
        actual_hire_date=hire_date,
        probation_months=prob_months,
        probation_start_date=hire_date,
        probation_end_date=probation_end,
        probation_status=ProbationStatus.IN_PROGRESS,
        employment_type=after_data.get("employment_type"),
        department=after_data.get("department"),
        position=after_data.get("position"),
        work_city=after_data.get("work_city"),
        work_mode=after_data.get("work_mode"),
        manager_name=after_data.get("manager_name"),
        team_name=after_data.get("team_name"),
        created_by=operator_id,
        updated_by=operator_id,
    )
    db.add(emp)
    db.flush()

    # 幂等生成跟进任务
    from .roster_commit_service import _generate_initialization_tasks
    _generate_initialization_tasks(db, emp.id, hire_date)


@_register(ConfirmationIssueCode.MISSING_HIRE_DATE)
def _handle_missing_hire_date(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理缺少入职日期。

    P0 规则：
    - 实际入职日期必填，不能晚于今天。
    - 不允许系统自行使用今天补齐。
    - 查找当前有效任职（PENDING / ACTIVE / SEPARATING），
      不获取任意历史记录（禁止用 .first() 取得 SEPARATED 记录）。
    - 没有当前任职时创建新记录。
    - 不允许把 SEPARATED 历史记录改回 ACTIVE。
    - 支持"已经入职"和"预计以后入职"两种场景。

    已经入职：
    - 创建新任职
    - status = ACTIVE
    - actual_hire_date = HR填写日期
    - 计算试用期
    - 生成尚未过期的跟进任务

    预计以后入职：
    - 创建 PENDING 任职
    - expected_hire_date = HR填写日期
    - actual_hire_date = null
    - 不生成正式试用期任务
    """
    if not after_data:
        raise ValidationError("缺少入职日期数据")

    hire_date_input = _parse_date(
        after_data.get("hire_date") or after_data.get("actual_hire_date")
    )
    if not hire_date_input:
        raise ValidationError("实际入职日期不能为空，请填写入职日期")

    today = datetime.now().date()

    # 判断是"已经入职"还是"预计以后入职"
    is_actual_hire = hire_date_input <= today
    if is_actual_hire:
        # 已经入职
        actual_hire_date = hire_date_input
        employment_status = EmploymentStatus.ACTIVE
        expected_hire_date = None
    else:
        # 预计以后入职
        actual_hire_date = None
        employment_status = EmploymentStatus.PENDING
        expected_hire_date = hire_date_input
        hire_date_input = hire_date_input

    # 查找当前有效任职（仅限 PENDING / ACTIVE / SEPARATING）
    current_active = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employee_id == item.employee_id,
            EmploymentRecord.employment_status.in_([
                EmploymentStatus.PENDING,
                EmploymentStatus.ACTIVE,
                EmploymentStatus.SEPARATING,
            ]),
            EmploymentRecord.is_deleted == False,
        )
        .first()
    )
    if current_active:
        # 更新已有有效任职的入职日期
        current_active.hire_date = hire_date_input
        current_active.actual_hire_date = actual_hire_date
        current_active.expected_hire_date = expected_hire_date
        current_active.employment_status = employment_status.value
        current_active.updated_by = operator_id
        current_active.updated_at = now
        employment = current_active
    else:
        # 创建新任职
        max_seq = (
            db.query(EmploymentRecord.employment_seq)
            .filter(EmploymentRecord.employee_id == item.employee_id)
            .order_by(EmploymentRecord.employment_seq.desc())
            .first()
        )
        employment_seq = (max_seq[0] if max_seq else 0) + 1

        probation_months = after_data.get("probation_months", 3)
        try:
            probation_months = int(probation_months)
        except (ValueError, TypeError):
            probation_months = 3

        from ..services.employment_service import calculate_probation_end_date

        if is_actual_hire and probation_months >= 1 and probation_months <= 6:
            probation_end = calculate_probation_end_date(hire_date_input, probation_months)
            probation_start = hire_date_input
            prob_status = ProbationStatus.IN_PROGRESS
        else:
            probation_end = None
            probation_start = None
            prob_status = ProbationStatus.NOT_STARTED

        employment = EmploymentRecord(
            employee_id=item.employee_id,
            employment_seq=employment_seq,
            employment_status=employment_status.value,
            hire_date=hire_date_input,
            actual_hire_date=actual_hire_date,
            expected_hire_date=expected_hire_date,
            probation_months=probation_months if is_actual_hire else 0,
            probation_start_date=probation_start,
            probation_end_date=probation_end,
            probation_status=prob_status.value,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(employment)
        db.flush()

    # 更新员工资料为完整
    employee = db.query(Employee).filter(Employee.id == item.employee_id).first()
    if employee:
        try:
            employee.profile_completeness_status = "COMPLETE"
        except Exception:
            pass

    # 已入职时生成跟进任务
    if is_actual_hire:
        from .roster_commit_service import _generate_initialization_tasks
        _generate_initialization_tasks(db, employment.id, hire_date_input)


@_register(ConfirmationIssueCode.EMPLOYEE_MISSING_FROM_ROSTER)
def _handle_employee_missing_from_roster(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理员工不在花名册中的提醒 —— 仅确认知晓。"""
    pass


@_register(ConfirmationIssueCode.SALARY_CHANGE)
def _handle_salary_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理薪酬变更确认 —— 薪酬记录已在提交时创建，确认即知晓。"""
    pass


@_register(ConfirmationIssueCode.HOUSEHOLD_REGISTRATION_CHANGE)
def _handle_household_registration_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理户籍地址变更确认。"""
    if not after_data:
        return
    new_value = after_data.get("household_registration")
    if new_value is None:
        return
    _update_profile_field(db, item.employee_id, "household_registration", new_value, operator_id, now)


@_register(ConfirmationIssueCode.RESIDENCE_ADDRESS_CHANGE)
def _handle_residence_address_change(
    db: DBSession,
    item: HrConfirmationItem,
    before_data: Any,
    after_data: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """处理居住地址变更确认。"""
    if not after_data:
        return
    new_value = after_data.get("residence_address")
    if new_value is None:
        return
    _update_profile_field(db, item.employee_id, "residence_address", new_value, operator_id, now)


# 为了兼容旧 issue_code，注册别名
_CONFIRMATION_HANDLERS["SEPARATION_DATE"] = _handle_pending_separation
_CONFIRMATION_HANDLERS["REEMPLOYMENT"] = _handle_possible_reemployment


# ============================================================
# 公共 API
# ============================================================


def _to_dict(item: HrConfirmationItem) -> dict[str, Any]:
    """将确认事项转为字典，解析 JSON 字段。"""
    data = item.dict()

    raw_before = data.pop("before_data_json", None)
    if raw_before:
        try:
            data["before_data"] = json.loads(raw_before)
        except (json.JSONDecodeError, TypeError):
            data["before_data"] = raw_before
    else:
        data["before_data"] = None

    raw_after = data.pop("after_data_json", None)
    if raw_after:
        try:
            data["after_data"] = json.loads(raw_after)
        except (json.JSONDecodeError, TypeError):
            data["after_data"] = raw_after
    else:
        data["after_data"] = None

    return data


def create_confirmation_item(
    db: DBSession,
    employee_id: int,
    employment_id: int | None,
    source_type: str,
    source_id: str | None,
    issue_code: str,
    title: str,
    description: str | None = None,
    before_data: Any = None,
    after_data: Any = None,
    import_batch_id: int | None = None,
    import_row_id: int | None = None,
) -> dict:
    """创建待确认事项。

    相同 employee_id + issue_code + source_id 的待确认事项视为重复，
    直接返回已有记录。
    """
    if source_id is not None:
        existing = db.query(HrConfirmationItem).filter(
            HrConfirmationItem.employee_id == employee_id,
            HrConfirmationItem.issue_code == issue_code,
            HrConfirmationItem.source_id == source_id,
            HrConfirmationItem.item_status == ConfirmationItemStatus.PENDING.value,
        ).first()
        if existing:
            return _to_dict(existing)

    now = datetime.now()

    item = HrConfirmationItem(
        employee_id=employee_id,
        employment_id=employment_id,
        source_type=source_type,
        source_id=source_id,
        issue_code=issue_code,
        title=title,
        description=description,
        before_data_json=json.dumps(before_data, default=str, ensure_ascii=False)
        if before_data is not None
        else None,
        after_data_json=json.dumps(after_data, default=str, ensure_ascii=False)
        if after_data is not None
        else None,
        import_batch_id=import_batch_id,
        import_row_id=import_row_id,
        item_status=ConfirmationItemStatus.PENDING,
        created_at=now,
    )
    db.add(item)
    db.flush()

    return _to_dict(item)


def list_confirmation_items(
    db: DBSession,
    status: str | None = None,
    employee_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int, int]:
    """分页查询待确认事项列表。"""
    query = db.query(HrConfirmationItem)

    if status:
        query = query.filter(HrConfirmationItem.item_status == status)
    if employee_id is not None:
        query = query.filter(HrConfirmationItem.employee_id == employee_id)

    total = query.count()

    pending_count = db.query(HrConfirmationItem).filter(
        HrConfirmationItem.item_status == ConfirmationItemStatus.PENDING.value,
    ).count()

    items = (
        query.order_by(HrConfirmationItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    employee_ids = {item.employee_id for item in items}
    employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all()
    employee_map = {e.id: e.name for e in employees}

    result = []
    for item in items:
        d = _to_dict(item)
        d["employee_name"] = employee_map.get(item.employee_id)
        result.append(d)

    return result, total, pending_count


def get_pending_count(db: DBSession) -> int:
    """获取待确认事项数量。"""
    return db.query(HrConfirmationItem).filter(
        HrConfirmationItem.item_status == ConfirmationItemStatus.PENDING.value,
    ).count()


def get_confirmation_item(db: DBSession, item_id: int) -> dict | None:
    """获取确认事项详情。"""
    item = db.query(HrConfirmationItem).filter(
        HrConfirmationItem.id == item_id,
    ).first()
    if not item:
        return None

    d = _to_dict(item)
    employee = db.query(Employee).filter(Employee.id == item.employee_id).first()
    d["employee_name"] = employee.name if employee else None
    return d


def _get_item(db: DBSession, item_id: int) -> HrConfirmationItem:
    """获取确认事项，不存在时抛异常。"""
    item = db.query(HrConfirmationItem).filter(
        HrConfirmationItem.id == item_id,
    ).first()
    if not item:
        raise ResourceNotFound(f"确认事项不存在: {item_id}")
    return item


def _ensure_pending(item: HrConfirmationItem) -> None:
    """确保事项处于待确认状态。"""
    if item.item_status != ConfirmationItemStatus.PENDING.value:
        raise InvalidStateTransition(
            f"确认事项状态不允许操作，当前状态: {item.item_status}"
        )


def _parse_json(data_json: str | None) -> Any:
    """安全解析 JSON 字符串。"""
    if not data_json:
        return None
    try:
        return json.loads(data_json)
    except (json.JSONDecodeError, TypeError):
        return None


def _update_profile_field(
    db: DBSession,
    employee_id: int,
    field_name: str,
    new_value: Any,
    operator_id: str,
    now: datetime,
) -> None:
    """更新员工档案字段。"""
    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id == employee_id,
        EmployeeProfile.is_deleted == False,
    ).first()

    if not profile:
        profile = EmployeeProfile(
            employee_id=employee_id,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(profile)

    setattr(profile, field_name, new_value)
    profile.updated_by = operator_id
    profile.updated_at = now
    db.flush()


# ============================================================
# 确认动作
# ============================================================


def confirm_item(
    db: DBSession,
    item_id: int,
    operator: dict,
    note: str | None = None,
) -> dict:
    """确认事项并执行业务动作。

    流程：
    1. 加载事项，检查状态为 PENDING。
    2. 查找对应处理器。
    3. 执行业务操作。
    4. 只有业务操作成功，才能改成 CONFIRMED。
    5. 业务操作失败时保持 PENDING。
    """
    item = _get_item(db, item_id)
    _ensure_pending(item)

    now = datetime.now()
    operator_id = operator.get("user_id", "system")
    before_item = _to_dict(item)

    before_data = _parse_json(item.before_data_json)
    after_data = _parse_json(item.after_data_json)

    issue_code = item.issue_code

    # 查找处理器
    handler = get_handler(issue_code)
    if handler is None:
        # 未知 issue_code —— 必须报错，不能假装确认成功
        raise InvalidStateTransition(
            f"不支持的确认事项类型: {issue_code}。"
            f"请确认系统版本一致或联系管理员。"
        )

    # 执行业务操作（失败时抛出异常）
    handler(db, item, before_data, after_data, operator_id, now)

    # 只有业务操作成功后，才能更新状态
    item.item_status = ConfirmationItemStatus.CONFIRMED.value
    item.handled_at = now

    db.flush()

    # 操作日志
    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.HR_CONFIRMATION.value,
        object_id=str(item.id),
        operation_type="CONFIRM",
        before_data=json.dumps(before_item, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(item), default=str, ensure_ascii=False),
        business_id=item.employee_id,
    )

    db.flush()
    return _to_dict(item)


def reject_item(
    db: DBSession,
    item_id: int,
    operator: dict,
    note: str | None = None,
) -> dict:
    """拒绝确认事项。"""
    item = _get_item(db, item_id)
    _ensure_pending(item)

    now = datetime.now()
    operator_id = operator.get("user_id", "system")
    before_item = _to_dict(item)

    item.item_status = ConfirmationItemStatus.REJECTED.value
    item.handled_at = now

    db.flush()

    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.HR_CONFIRMATION.value,
        object_id=str(item.id),
        operation_type="REJECT",
        before_data=json.dumps(before_item, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(item), default=str, ensure_ascii=False),
        business_id=item.employee_id,
    )

    db.flush()
    return _to_dict(item)


def ignore_item(
    db: DBSession,
    item_id: int,
    operator: dict,
    note: str | None = None,
) -> dict:
    """忽略确认事项。"""
    item = _get_item(db, item_id)
    _ensure_pending(item)

    now = datetime.now()
    operator_id = operator.get("user_id", "system")
    before_item = _to_dict(item)

    item.item_status = ConfirmationItemStatus.IGNORED.value
    item.handled_at = now

    db.flush()

    create_log(
        db=db,
        operator_id=operator_id,
        object_type=OperationObjectType.HR_CONFIRMATION.value,
        object_id=str(item.id),
        operation_type="IGNORE",
        before_data=json.dumps(before_item, default=str, ensure_ascii=False),
        after_data=json.dumps(_to_dict(item), default=str, ensure_ascii=False),
        business_id=item.employee_id,
    )

    db.flush()
    return _to_dict(item)


# ============================================================
# 工具函数（使用统一 date_utils 模块）
# ============================================================
# _parse_date 已从 date_utils 导入为 _parse_date

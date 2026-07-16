"""HR 待确认事项服务。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..enums import (
    AccountStatus,
    ConfirmationItemStatus,
    EmploymentStatus,
    OperationObjectType,
)
from ..exceptions import (
    InvalidStateTransition,
    ResourceNotFound,
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
from .operation_log_service import create_log


def _to_dict(item: HrConfirmationItem) -> dict[str, Any]:
    """将确认事项转为字典，解析 JSON 字段。"""
    data = item.dict()

    # 解析 before_data_json
    raw_before = data.pop("before_data_json", None)
    if raw_before:
        try:
            data["before_data"] = json.loads(raw_before)
        except (json.JSONDecodeError, TypeError):
            data["before_data"] = raw_before
    else:
        data["before_data"] = None

    # 解析 after_data_json
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
) -> dict:
    """创建待确认事项。

    相同 employee_id + issue_code + source_id 的待确认事项视为重复，
    直接返回已有记录。
    """
    # 重复检测：相同员工 + issue_code + source_id
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
    """分页查询待确认事项列表。

    返回 (items, total, pending_count)。
    """
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

    # 批量加载员工姓名
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


def confirm_item(
    db: DBSession,
    item_id: int,
    operator: dict,
    note: str | None = None,
) -> dict:
    """确认事项并执行业务动作。"""
    item = _get_item(db, item_id)
    _ensure_pending(item)

    now = datetime.now()
    operator_id = operator.get("user_id", "system")
    before_item = _to_dict(item)

    before_data = _parse_json(item.before_data_json)
    after_data = _parse_json(item.after_data_json)

    issue_code = item.issue_code

    # 根据 issue_code 执行业务动作
    if issue_code == "CONTRACT_CHANGE":
        _handle_contract_change(db, item, after_data, operator_id, now)
    elif issue_code in ("NEW_BANK_ACCOUNT", "NEW_ALIPAY"):
        _handle_new_financial_account(db, item, after_data, operator_id, now)
    elif issue_code == "IDENTITY_CARD_CHANGE":
        _handle_profile_update(db, item, "identity_card", after_data, operator_id, now)
    elif issue_code == "BIRTH_DATE_CHANGE":
        _handle_profile_update(db, item, "birth_date", after_data, operator_id, now)
    elif issue_code == "GENDER_CHANGE":
        _handle_profile_update(db, item, "gender", after_data, operator_id, now)
    elif issue_code == "SEPARATION_DATE":
        _handle_separation_date(db, item, after_data, operator_id, now)
    elif issue_code == "REEMPLOYMENT":
        _handle_reemployment(db, item, after_data, operator_id, now)
    elif issue_code in ("MISSING_HIRE_DATE", "EMPLOYEE_NOT_IN_ROSTER"):
        # 仅确认知晓，无需执行业务动作
        pass
    else:
        # 未知 issue_code，非阻断，仅记录日志
        pass

    # 更新确认事项状态
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


# ---------------------------------------------------------------------------
# 业务动作处理函数（按 issue_code 分发）
# ---------------------------------------------------------------------------


def _handle_contract_change(
    db: DBSession,
    item: HrConfirmationItem,
    after_data: dict | None,
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


def _handle_new_financial_account(
    db: DBSession,
    item: HrConfirmationItem,
    after_data: dict | None,
    operator_id: str,
    now: datetime,
) -> None:
    """处理新财务账户：激活账户并记录确认时间。"""
    if not after_data:
        return

    account_query = db.query(EmployeeFinancialAccount).filter(
        EmployeeFinancialAccount.employee_id == item.employee_id,
        EmployeeFinancialAccount.is_deleted == False,
    )

    # 优先通过 source_id（账户 ID）查找
    if item.source_id:
        try:
            account_id = int(item.source_id)
            account_query = account_query.filter(
                EmployeeFinancialAccount.id == account_id,
            )
        except (ValueError, TypeError):
            pass
    else:
        # 通过 after_data 中的 account_no 查找
        account_no = after_data.get("account_no")
        if account_no:
            account_query = account_query.filter(
                EmployeeFinancialAccount.account_no == account_no,
            )
        else:
            return

    account = account_query.first()

    if account:
        account.account_status = AccountStatus.ACTIVE.value
        account.confirmed_at = now
        account.updated_by = operator_id
        account.updated_at = now
    else:
        # 账户记录不存在时自动创建
        account_type = after_data.get(
            "account_type",
            "BANK" if item.issue_code == "NEW_BANK_ACCOUNT" else "ALIPAY",
        )
        account = EmployeeFinancialAccount(
            employee_id=item.employee_id,
            account_type=account_type,
            account_no=after_data.get("account_no") or "",
            bank_name=after_data.get("bank_name"),
            is_primary=after_data.get("is_primary", False),
            account_status=AccountStatus.ACTIVE.value,
            confirmed_at=now,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(account)
        db.flush()


def _handle_profile_update(
    db: DBSession,
    item: HrConfirmationItem,
    field_name: str,
    after_data: dict | None,
    operator_id: str,
    now: datetime,
) -> None:
    """更新员工档案字段。"""
    if not after_data:
        return

    new_value = after_data.get(field_name)
    if new_value is None:
        return

    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.employee_id == item.employee_id,
        EmployeeProfile.is_deleted == False,
    ).first()

    if not profile:
        profile = EmployeeProfile(
            employee_id=item.employee_id,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(profile)

    setattr(profile, field_name, new_value)
    profile.updated_by = operator_id
    profile.updated_at = now
    db.flush()


def _handle_separation_date(
    db: DBSession,
    item: HrConfirmationItem,
    after_data: dict | None,
    operator_id: str,
    now: datetime,
) -> None:
    """处理离职日期确认。"""
    if not after_data:
        return

    planned_date = _parse_date(
        after_data.get("planned_separation_date")
        or after_data.get("separation_date"),
    )
    if not planned_date:
        return

    # 更新任职记录的预计离职日期
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

        # 创建离职记录
        record = SeparationRecord(
            employment_id=item.employment_id,
            planned_separation_date=planned_date,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(record)
        db.flush()


def _handle_reemployment(
    db: DBSession,
    item: HrConfirmationItem,
    after_data: dict | None,
    operator_id: str,
    now: datetime,
) -> None:
    """处理重新入职：创建新任职记录。"""
    if not after_data:
        return

    # 计算新的 employment_seq
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

    hire_date = _parse_date(
        after_data.get("hire_date") or after_data.get("actual_hire_date"),
    )
    actual_hire_date = _parse_date(
        after_data.get("actual_hire_date") or after_data.get("hire_date"),
    )

    emp = EmploymentRecord(
        employee_id=item.employee_id,
        employment_seq=next_seq,
        employment_status=EmploymentStatus.ACTIVE.value,
        hire_date=hire_date or datetime.now().date(),
        actual_hire_date=actual_hire_date,
        expected_hire_date=_parse_date(after_data.get("expected_hire_date")),
        probation_months=after_data.get("probation_months", 3),
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


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _parse_date(value: Any) -> Any:
    """安全解析日期值。

    支持传入 date 对象、datetime 对象或 ISO 格式字符串。
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except (ValueError, IndexError):
            return None
    return None

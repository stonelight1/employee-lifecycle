"""花名册导入统一字段策略定义。

所有模块（预览、提交、确认、撤销、前端）必须读取同一份策略。
禁止在各模块中分别维护字段列表。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..enums import ConfirmationIssueCode, FieldUpdateMode


@dataclass(frozen=True)
class RosterFieldPolicy:
    """字段策略 —— 描述花名册导入中每个字段的行为。

    Attributes:
        field_key: 系统内部字段键名。
        target_model: 目标模型名（employee / profile / employment / contract / account / salary / note）。
        update_mode: 更新模式。
        empty_behavior: 空值行为（"KEEP_OLD" / "SET_NULL" / "IGNORE" / "WARN_AND_KEEP"）。
        history_required: 是否记录属性变更历史。
        confirmation_issue_code: 需要确认时的 issue_code，None 表示无需确认。
        labels: 展示标签（前端用）。
    """
    field_key: str
    target_model: str
    update_mode: FieldUpdateMode
    empty_behavior: str = "IGNORE"
    history_required: bool = True
    confirmation_issue_code: str | None = None
    labels: tuple[str, ...] = ()


# ── 策略注册表 ──────────────────────────────────────────────────────────

_FIELD_POLICIES: dict[str, RosterFieldPolicy] = {}


def _reg(policy: RosterFieldPolicy) -> RosterFieldPolicy:
    """注册一条字段策略。"""
    _FIELD_POLICIES[policy.field_key] = policy
    return policy


# ========================================================================
# 员工基本资料
# ========================================================================

# 姓名 —— 只在 HR 确认后才更新
_reg(RosterFieldPolicy(
    field_key="name",
    target_model="employee",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.NAME_CHANGE,
    labels=("姓名",),
))

# 手机号 —— 自动更新，无需确认
_reg(RosterFieldPolicy(
    field_key="mobile",
    target_model="employee",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("手机号",),
))

# 邮箱 —— 自动更新，无需确认
_reg(RosterFieldPolicy(
    field_key="email",
    target_model="employee",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("邮箱",),
))

# 员工编号 —— 自动更新
_reg(RosterFieldPolicy(
    field_key="employee_no",
    target_model="employee",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("员工编号",),
))

# 身份证号 —— 只在 HR 确认后才更新
_reg(RosterFieldPolicy(
    field_key="identity_card",
    target_model="profile",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.IDENTITY_CARD_CHANGE,
    labels=("身份证号", "身份证号码"),
))

# 出生日期 —— 只在 HR 确认后才更新
_reg(RosterFieldPolicy(
    field_key="birth_date",
    target_model="profile",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.BIRTH_DATE_CHANGE,
    labels=("出生日期", "生日"),
))

# 性别 —— 只在 HR 确认后才更新
_reg(RosterFieldPolicy(
    field_key="gender",
    target_model="profile",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.GENDER_CHANGE,
    labels=("性别",),
))

# 户籍地址 —— 自动更新
_reg(RosterFieldPolicy(
    field_key="household_registration",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.HOUSEHOLD_REGISTRATION_CHANGE,
    labels=("户籍地址", "户籍所在地"),
))

# 居住地址 —— 自动更新
_reg(RosterFieldPolicy(
    field_key="residence_address",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.RESIDENCE_ADDRESS_CHANGE,
    labels=("居住地址", "现住址"),
))

# 户口类型 —— 自动更新
_reg(RosterFieldPolicy(
    field_key="household_type",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("户口类型", "户籍类型"),
))

_reg(RosterFieldPolicy(
    field_key="education_level",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("学历",),
))

_reg(RosterFieldPolicy(
    field_key="graduation_school",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("毕业院校", "毕业学校"),
))

_reg(RosterFieldPolicy(
    field_key="major",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("专业",),
))

_reg(RosterFieldPolicy(
    field_key="social_insurance_status",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("社保状态",),
))

_reg(RosterFieldPolicy(
    field_key="housing_fund_status",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("公积金状态",),
))

_reg(RosterFieldPolicy(
    field_key="social_insurance_policy",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("社保缴纳规则",),
))

_reg(RosterFieldPolicy(
    field_key="housing_fund_policy",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("公积金缴纳规则",),
))

_reg(RosterFieldPolicy(
    field_key="social_insurance_start_date",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    empty_behavior="SET_NULL",
    labels=("社保开始日期",),
))

_reg(RosterFieldPolicy(
    field_key="housing_fund_start_date",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    empty_behavior="SET_NULL",
    labels=("公积金开始日期",),
))

_reg(RosterFieldPolicy(
    field_key="benefit_raw_text",
    target_model="profile",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("五险一金原文",),
))

# ========================================================================
# 任职信息
# ========================================================================

_reg(RosterFieldPolicy(
    field_key="department",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("部门",),
))

_reg(RosterFieldPolicy(
    field_key="position",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("岗位", "职位"),
))

_reg(RosterFieldPolicy(
    field_key="team_name",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("团队", "分队"),
))

_reg(RosterFieldPolicy(
    field_key="manager_name",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("直属负责人", "直属上级"),
))

_reg(RosterFieldPolicy(
    field_key="employment_type",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("用工类型", "员工类型"),
))

_reg(RosterFieldPolicy(
    field_key="work_city",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("工作城市",),
))

_reg(RosterFieldPolicy(
    field_key="work_mode",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("工作模式", "办公方式"),
))

# ========================================================================
# 合同信息 —— 只在 HR 确认后才更新
# ========================================================================

_reg(RosterFieldPolicy(
    field_key="contract_status",
    target_model="contract",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.CONTRACT_CHANGE,
    labels=("合同状态",),
))

_reg(RosterFieldPolicy(
    field_key="signing_company",
    target_model="contract",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.CONTRACT_COMPANY_CHANGE,
    labels=("签订公司", "签约公司"),
))

_reg(RosterFieldPolicy(
    field_key="contract_type",
    target_model="contract",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.CONTRACT_CHANGE,
    labels=("合同类型",),
))

_reg(RosterFieldPolicy(
    field_key="contract_end_date",
    target_model="contract",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.CONTRACT_TERM_CHANGE,
    labels=("合同到期日", "合同截止日期"),
))

_reg(RosterFieldPolicy(
    field_key="signing_sequence",
    target_model="contract",
    update_mode=FieldUpdateMode.RAW_ONLY,
    labels=("签订次数",),
))

# ========================================================================
# 财务账户 —— 不覆盖，追加记录前需 HR 确认
# ========================================================================

_reg(RosterFieldPolicy(
    field_key="bank_card",
    target_model="account",
    update_mode=FieldUpdateMode.APPEND_RECORD,
    confirmation_issue_code=ConfirmationIssueCode.NEW_BANK_ACCOUNT,
    labels=("银行卡号", "银行卡"),
))

_reg(RosterFieldPolicy(
    field_key="bank_name",
    target_model="account",
    update_mode=FieldUpdateMode.RAW_ONLY,
    labels=("开户银行",),
))

_reg(RosterFieldPolicy(
    field_key="alipay",
    target_model="account",
    update_mode=FieldUpdateMode.APPEND_RECORD,
    confirmation_issue_code=ConfirmationIssueCode.NEW_ALIPAY_ACCOUNT,
    labels=("支付宝账号", "支付宝"),
))

# ========================================================================
# 薪酬 —— 自动创建记录
# ========================================================================

_reg(RosterFieldPolicy(
    field_key="salary_text",
    target_model="salary",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("薪资", "薪酬"),
))

_reg(RosterFieldPolicy(
    field_key="raw_salary_text",
    target_model="salary",
    update_mode=FieldUpdateMode.RAW_ONLY,
    labels=("薪酬原文",),
))

# ========================================================================
# 入职与离职 —— 特殊逻辑
# ========================================================================

_reg(RosterFieldPolicy(
    field_key="hire_date",
    target_model="employment",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.ACTUAL_HIRE_DATE_CHANGE,
    labels=("入职日期", "实际入职日期"),
))

_reg(RosterFieldPolicy(
    field_key="expected_hire_date",
    target_model="employment",
    update_mode=FieldUpdateMode.CALCULATED_ONLY,
    labels=("预计入职日期",),
))

_reg(RosterFieldPolicy(
    field_key="regularization_date",
    target_model="employment",
    update_mode=FieldUpdateMode.CALCULATED_ONLY,
    labels=("转正日期",),
))

_reg(RosterFieldPolicy(
    field_key="probation_months",
    target_model="employment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("试用期(月)", "试用期月数"),
))

_reg(RosterFieldPolicy(
    field_key="separation_date",
    target_model="employment",
    update_mode=FieldUpdateMode.CONFIRM_BEFORE_UPDATE,
    confirmation_issue_code=ConfirmationIssueCode.PENDING_SEPARATION,
    labels=("离职日期",),
))

# ========================================================================
# 测评与备注
# ========================================================================

_reg(RosterFieldPolicy(
    field_key="mbti",
    target_model="assessment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("MBTI",),
))

_reg(RosterFieldPolicy(
    field_key="pdp",
    target_model="assessment",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("PDP",),
))

_reg(RosterFieldPolicy(
    field_key="remark",
    target_model="note",
    update_mode=FieldUpdateMode.AUTO_UPDATE,
    labels=("备注", "备注信息"),
))

_reg(RosterFieldPolicy(
    field_key="age",
    target_model=None,
    update_mode=FieldUpdateMode.CALCULATED_ONLY,
    labels=("年龄",),
))

_reg(RosterFieldPolicy(
    field_key="work_age",
    target_model=None,
    update_mode=FieldUpdateMode.CALCULATED_ONLY,
    labels=("司龄", "工龄"),
))


# ========================================================================
# 查询函数
# ========================================================================


def get_field_policy(field_key: str) -> RosterFieldPolicy | None:
    """获取指定字段的策略，None 表示该字段未被定义。"""
    return _FIELD_POLICIES.get(field_key)


def get_auto_update_fields() -> set[str]:
    """获取自动更新字段集合。"""
    return {
        fk for fk, fp in _FIELD_POLICIES.items()
        if fp.update_mode == FieldUpdateMode.AUTO_UPDATE
    }


def get_confirmation_fields() -> set[str]:
    """获取需要 HR 确认的字段集合。"""
    return {
        fk for fk, fp in _FIELD_POLICIES.items()
        if fp.update_mode == FieldUpdateMode.CONFIRM_BEFORE_UPDATE
    }


def get_append_fields() -> set[str]:
    """获取追加记录字段集合（不覆盖，需确认）。"""
    return {
        fk for fk, fp in _FIELD_POLICIES.items()
        if fp.update_mode == FieldUpdateMode.APPEND_RECORD
    }


def get_all_field_keys() -> set[str]:
    """获取所有已注册字段键。"""
    return set(_FIELD_POLICIES.keys())

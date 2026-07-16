"""花名册字段映射服务。"""

from __future__ import annotations

import difflib
import json
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session as DBSession

from ..exceptions import Conflict, ResourceNotFound
from ..models import OrganizationReference, RosterColumnAlias, RosterImportBatch, RosterValueAlias
from ..services.normalize import normalize_name


# ─── 字段定义 ────────────────────────────────────────────────────────────────

DEFAULT_FIELD_DEFINITIONS: list[dict] = [
    {"key": "name", "label": "姓名", "required": True, "description": "员工姓名", "example_values": "张三"},
    {"key": "mobile", "label": "手机号", "required": False, "description": "手机号码", "example_values": "13800138000"},
    {"key": "email", "label": "邮箱", "required": False, "description": "电子邮箱", "example_values": "zhang@example.com"},
    {"key": "identity_card", "label": "身份证号", "required": False, "description": "身份证号码", "example_values": "110101199001011234"},
    {"key": "gender", "label": "性别", "required": False, "description": "性别", "example_values": "男/女"},
    {"key": "birth_date", "label": "出生日期", "required": False, "description": "出生日期", "example_values": "1990-01-01"},
    {"key": "hire_date", "label": "入职日期", "required": False, "description": "实际入职日期", "example_values": "2026-01-01"},
    {"key": "expected_hire_date", "label": "预计入职日期", "required": False, "description": "预计入职日期", "example_values": "2026-01-01"},
    {"key": "department", "label": "部门", "required": False, "description": "所属部门", "example_values": "技术部"},
    {"key": "position", "label": "岗位", "required": False, "description": "岗位名称", "example_values": "软件工程师"},
    {"key": "team_name", "label": "分队", "required": False, "description": "分队/小组", "example_values": "前端组"},
    {"key": "manager_name", "label": "直属负责人", "required": False, "description": "直属上级", "example_values": "李四"},
    {"key": "employment_type", "label": "员工类型", "required": False, "description": "正式/实习/外包/合作", "example_values": "正式"},
    {"key": "work_city", "label": "工作城市", "required": False, "description": "工作城市/地区", "example_values": "北京"},
    {"key": "work_mode", "label": "办公方式", "required": False, "description": "办公方式", "example_values": "远程/ onsite"},
    {"key": "probation_months", "label": "试用期(月)", "required": False, "description": "试用期月数", "example_values": "3"},
    {"key": "regularization_date", "label": "转正日期", "required": False, "description": "实际转正日期", "example_values": "2026-04-01"},
    {"key": "separation_date", "label": "离职日期", "required": False, "description": "离职日期", "example_values": "2026-12-31"},
    {"key": "employment_status", "label": "在职状态", "required": False, "description": "在职/离职", "example_values": "在职"},
    {"key": "contract_status", "label": "合同状态", "required": False, "description": "合同状态", "example_values": "已签"},
    {"key": "signing_company", "label": "签订公司", "required": False, "description": "合同签订公司", "example_values": "XX科技有限公司"},
    {"key": "contract_type", "label": "合同类型", "required": False, "description": "固定期限/无固定期限", "example_values": "无固定期限"},
    {"key": "contract_end_date", "label": "合同到期日", "required": False, "description": "合同到期日期", "example_values": "2029-01-01"},
    {"key": "signing_sequence", "label": "签订次数", "required": False, "description": "签订次数", "example_values": "1"},
    {"key": "bank_card", "label": "银行卡号", "required": False, "description": "银行卡号", "example_values": "6222021234567890"},
    {"key": "bank_name", "label": "开户银行", "required": False, "description": "开户银行名称", "example_values": "中国工商银行"},
    {"key": "alipay", "label": "支付宝账号", "required": False, "description": "支付宝账号", "example_values": "138@example.com"},
    {"key": "benefit_raw_text", "label": "五险一金原文", "required": False, "description": "花名册五险一金缴纳原文", "example_values": "五险一金（入职）"},
    {"key": "social_insurance_policy", "label": "社保缴纳规则", "required": False, "description": "社保从入职/转正开始或不缴纳", "example_values": "FROM_HIRE_DATE"},
    {"key": "housing_fund_policy", "label": "公积金缴纳规则", "required": False, "description": "公积金从入职/转正开始或不缴纳", "example_values": "NOT_PROVIDED"},
    {"key": "social_insurance_status", "label": "社保状态", "required": False, "description": "五险一金缴纳状态", "example_values": "正常缴纳"},
    {"key": "housing_fund_status", "label": "公积金状态", "required": False, "description": "公积金缴纳状态", "example_values": "正常缴纳"},
    {"key": "social_insurance_start_date", "label": "社保开始日期", "required": False, "description": "社保实际开始缴纳日期", "example_values": "2026-01-01"},
    {"key": "housing_fund_start_date", "label": "公积金开始日期", "required": False, "description": "公积金实际开始缴纳日期", "example_values": "2026-01-01"},
    {"key": "household_registration", "label": "户籍", "required": False, "description": "户籍所在地", "example_values": "北京市朝阳区"},
    {"key": "residence_address", "label": "居住地址", "required": False, "description": "现居住地址", "example_values": "北京市海淀区"},
    {"key": "household_type", "label": "户口类型", "required": False, "description": "城镇/农村", "example_values": "城镇"},
    {"key": "education_level", "label": "学历", "required": False, "description": "最高学历", "example_values": "本科"},
    {"key": "graduation_school", "label": "毕业院校", "required": False, "description": "毕业院校", "example_values": "XX大学"},
    {"key": "major", "label": "专业", "required": False, "description": "所学专业", "example_values": "计算机科学"},
    {"key": "age", "label": "年龄", "required": False, "description": "年龄(仅校验)", "example_values": "30"},
    {"key": "work_age", "label": "司龄", "required": False, "description": "司龄(仅校验)", "example_values": "2年"},
    {"key": "raw_salary_text", "label": "薪资", "required": False, "description": "现底薪/薪资原文", "example_values": "试用期7000，转正8000"},
    {"key": "mbti", "label": "MBTI", "required": False, "description": "MBTI测评结果", "example_values": "INTJ"},
    {"key": "pdp", "label": "PDP", "required": False, "description": "PDP测评结果", "example_values": "老虎型"},
    {"key": "remark", "label": "备注", "required": False, "description": "备注信息", "example_values": "优秀员工"},
    {"key": "employee_no", "label": "员工编号", "required": False, "description": "员工编号", "example_values": "EMP001"},
]


# ─── 默认表头别名映射 ────────────────────────────────────────────────────────

DEFAULT_ALIASES: dict[str, str] = {
    # 姓名
    "姓名": "name",
    "员工姓名": "name",
    "名称": "name",
    "名字": "name",
    "员工名称": "name",
    "员工名字": "name",
    # 手机号
    "手机号码": "mobile",
    "手机号": "mobile",
    "电话号码": "mobile",
    "联系电话": "mobile",
    "电话": "mobile",
    "手机": "mobile",
    "移动电话": "mobile",
    # 邮箱
    "邮箱": "email",
    "电子邮箱": "email",
    "邮件": "email",
    "电子邮件": "email",
    # 身份证
    "身份证号": "identity_card",
    "身份证号码": "identity_card",
    "身份证": "identity_card",
    "证件号": "identity_card",
    "证件号码": "identity_card",
    "证件类型": "__skip__",  # will get filtered out
    # 性别
    "性别": "gender",
    # 出生日期
    "出生日期": "birth_date",
    "生日": "birth_date",
    "出生年月": "birth_date",
    # 入职日期
    "入职日期": "hire_date",
    "入职时间": "hire_date",
    "入职日": "hire_date",
    "实际入职日期": "hire_date",
    # 预计入职日期
    "预计入职日期": "expected_hire_date",
    "预计入职时间": "expected_hire_date",
    "预期入职日期": "expected_hire_date",
    # 部门
    "部门": "department",
    "所属部门": "department",
    "部门名称": "department",
    # 岗位
    "岗位": "position",
    "职位": "position",
    "工作岗位": "position",
    "岗位名称": "position",
    "职务": "position",
    # 分队
    "分队": "team_name",
    "小组": "team_name",
    "团队": "team_name",
    "组别": "team_name",
    "所属分队": "team_name",
    # 直属负责人
    "直属负责人": "manager_name",
    "直属上级": "manager_name",
    "上级": "manager_name",
    "直接上级": "manager_name",
    "汇报对象": "manager_name",
    "主管": "manager_name",
    # 员工类型
    "员工类型": "employment_type",
    "人员类型": "employment_type",
    "用工类型": "employment_type",
    "用工形式": "employment_type",
    "员工性质": "employment_type",
    # 工作城市
    "工作城市": "work_city",
    "城市": "work_city",
    "工作地点": "work_city",
    "工作地区": "work_city",
    "办公城市": "work_city",
    # 办公方式
    "办公方式": "work_mode",
    "工作方式": "work_mode",
    "办公模式": "work_mode",
    "工作模式": "work_mode",
    # 试用期
    "试用期(月)": "probation_months",
    "试用期": "probation_months",
    "试用期月数": "probation_months",
    "试用时长": "probation_months",
    # 转正日期
    "转正日期": "regularization_date",
    "转正时间": "regularization_date",
    "转正日": "regularization_date",
    # 离职日期
    "离职日期": "separation_date",
    "离职时间": "separation_date",
    "离职日": "separation_date",
    "最后工作日": "separation_date",
    # 在职状态
    "在职状态": "employment_status",
    "员工状态": "employment_status",
    "是否在职": "employment_status",
    "状态": "employment_status",
    # 合同状态
    "合同状态": "contract_status",
    "签订状态": "contract_status",
    # 签订公司
    "签订公司": "signing_company",
    "签约公司": "signing_company",
    "合同公司": "signing_company",
    "用人单位": "signing_company",
    # 合同类型
    "合同类型": "contract_type",
    "劳动合同类型": "contract_type",
    # 合同到期日
    "合同到期日": "contract_end_date",
    "合同截止日期": "contract_end_date",
    "合同到期时间": "contract_end_date",
    # 签订次数
    "签订次数": "signing_sequence",
    "签约次数": "signing_sequence",
    "第几次签订": "signing_sequence",
    # 银行卡
    "银行卡号": "bank_card",
    "银行卡": "bank_card",
    "银行账号": "bank_card",
    "卡号": "bank_card",
    # 开户银行
    "开户银行": "bank_name",
    "银行名称": "bank_name",
    "开户行": "bank_name",
    # 支付宝
    "支付宝账号": "alipay",
    "支付宝": "alipay",
    # 社保状态
    "五险一金缴纳": "benefit_raw_text",
    "五险一金": "benefit_raw_text",
    "社保公积金": "benefit_raw_text",
    "社保和公积金": "benefit_raw_text",
    "社保状态": "social_insurance_status",
    "五险状态": "social_insurance_status",
    "社保": "social_insurance_status",
    # 公积金状态
    "公积金状态": "housing_fund_status",
    "住房公积金状态": "housing_fund_status",
    "公积金": "housing_fund_status",
    # 户籍
    "户籍": "household_registration",
    "户籍所在地": "household_registration",
    "户口所在地": "household_registration",
    # 居住地址
    "居住地址": "residence_address",
    "现住址": "residence_address",
    "现居住地址": "residence_address",
    "通讯地址": "residence_address",
    # 户口类型
    "户口类型": "household_type",
    "户籍类型": "household_type",
    # 学历
    "学历": "education_level",
    "最高学历": "education_level",
    "文化程度": "education_level",
    # 毕业院校
    "毕业院校": "graduation_school",
    "学校": "graduation_school",
    "院校": "graduation_school",
    "毕业学校": "graduation_school",
    # 专业
    "专业": "major",
    "所学专业": "major",
    "主修专业": "major",
    # 年龄
    "年龄": "age",
    # 司龄
    "司龄": "work_age",
    "工龄": "work_age",
    # 薪资
    "薪资": "raw_salary_text",
    "工资": "raw_salary_text",
    "薪酬": "raw_salary_text",
    "底薪": "raw_salary_text",
    "现薪资": "raw_salary_text",
    "现底薪": "raw_salary_text",
    "现底薪（默认含30kpi）": "raw_salary_text",
    # MBTI
    "mbti": "mbti",
    "MBTI": "mbti",
    # PDP
    "pdp": "pdp",
    "PDP": "pdp",
    # 备注
    "备注": "remark",
    "备注信息": "remark",
    "备注说明": "remark",
    # 员工编号
    "员工编号": "employee_no",
    "工号": "employee_no",
    "员工ID": "employee_no",
    "编号": "employee_no",
    "员工号": "employee_no",
    # 日期格式列(不映射到具体字段，仅在特殊场景使用)
    "入职月份": "__skip__",
    "入职年份": "__skip__",
    "date": "__skip__",
    "序号": "__skip__",
    "no": "__skip__",
    "NO": "__skip__",
}


def _field_key_set() -> set[str]:
    """返回所有有效的 field_key 集合。"""
    return {f["key"] for f in DEFAULT_FIELD_DEFINITIONS}


def _aliases_by_field() -> dict[str, list[str]]:
    """返回 field_key -> [normalized_alias_header, ...] 的映射。"""
    result: dict[str, list[str]] = {}
    for alias_header, field_key in DEFAULT_ALIASES.items():
        if field_key == "__skip__":
            continue
        result.setdefault(field_key, []).append(normalize_header(alias_header))
    return result


# ─── 标准化工具 ────────────────────────────────────────────────────────────────


def normalize_header(text: str) -> str:
    """标准化表头文本：去除首尾空格、统一全角空格、压缩连续空白、转小写。"""
    if not text:
        return ""
    text = text.strip()
    text = text.replace("　", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.lower()
    return text


def normalize_value(value: str) -> str:
    """标准化值文本：去除首尾空格、统一全角空格、压缩连续空白。"""
    if not value:
        return ""
    value = value.strip()
    value = value.replace("　", " ")
    value = re.sub(r"\s+", " ", value)
    return value


# ─── 字段定义查询 ─────────────────────────────────────────────────────────────


def get_field_definitions() -> list[dict]:
    """返回系统所有字段定义列表。"""
    return list(DEFAULT_FIELD_DEFINITIONS)


# ─── 自动检测映射 ─────────────────────────────────────────────────────────────


def auto_detect_mappings(headers: list[str]) -> dict[str, str | None]:
    """根据 DEFAULT_ALIASES 自动检测每一列表头对应的字段键。

    匹配策略（按优先级）：
    1. 精确匹配（标准化后直接查 DEFAULT_ALIASES）。
    2. 去除常见后缀（“/说明”“(必填)”“:”等）后匹配。
    3. 模糊匹配（difflib 相似度 >= 0.6）。
    4. 仍不匹配 => None。

    Parameters
    ----------
    headers : list[str]
        Excel 表头行原始文本列表。

    Returns
    -------
    dict[str, str | None]
        header -> field_key（未知列为 None）的映射。
    """
    # 构建标准化后的 alias 查找结构
    # normalized_alias -> field_key (排除 __skip__)
    normalized_alias_map: dict[str, str] = {}
    for alias_header, field_key in DEFAULT_ALIASES.items():
        if field_key == "__skip__":
            continue
        normalized_alias_map[normalize_header(alias_header)] = field_key

    # 所有标准化后的 alias key 列表（用于模糊匹配）
    all_normalized_aliases = list(normalized_alias_map.keys())

    result: dict[str, str | None] = {}

    for raw_header in headers:
        matched = _match_single_header(raw_header, normalized_alias_map, all_normalized_aliases)
        result[raw_header] = matched

    return result


def _match_single_header(
    raw_header: str,
    normalized_alias_map: dict[str, str],
    all_normalized_aliases: list[str],
) -> str | None:
    """对单个表头执行多级匹配，返回 field_key 或 None。"""
    # 移除空白尾缀（多余检查，normalize 已做）
    norm = normalize_header(raw_header)
    if not norm:
        return None

    # 1) 精确匹配
    if norm in normalized_alias_map:
        return normalized_alias_map[norm]

    # 2) 去除常见后缀后匹配
    stripped = _strip_common_suffixes(norm)
    if stripped != norm and stripped in normalized_alias_map:
        return normalized_alias_map[stripped]

    # 3) 去除常见前缀后匹配
    cleaned = _strip_common_prefixes(norm)
    if cleaned != norm and cleaned in normalized_alias_map:
        return normalized_alias_map[cleaned]

    # 4) 模糊匹配 —— 使用 difflib
    close = difflib.get_close_matches(norm, all_normalized_aliases, n=1, cutoff=0.6)
    if close:
        return normalized_alias_map[close[0]]

    # 5) 模糊匹配 cleaned 版本
    if cleaned != norm:
        close2 = difflib.get_close_matches(cleaned, all_normalized_aliases, n=1, cutoff=0.6)
        if close2:
            return normalized_alias_map[close2[0]]

    return None


def _strip_common_suffixes(text: str) -> str:
    """去除常见后缀。"""
    # 需要处理 sorted by length desc 以避免短后缀截断过早
    suffixes = [
        "（必填）",
        "(必填)",
        "（选填）",
        "(选填)",
        "（说明）",
        "(说明)",
        "/说明",
        "：",
        ":",
    ]
    result = text
    for suffix in sorted(suffixes, key=len, reverse=True):
        if result.endswith(suffix):
            result = result[: -len(suffix)]
            break
    return result.strip()


def _strip_common_prefixes(text: str) -> str:
    """去除常见前缀。"""
    prefixes = ["员工", "人员"]
    result = text
    for prefix in sorted(prefixes, key=len, reverse=True):
        if result.startswith(prefix):
            result = result[len(prefix) :]
            break
    return result.strip()


# ─── 批次映射管理 ─────────────────────────────────────────────────────────────


def _to_dict(model) -> dict[str, Any]:
    """将模型实例转为字典。"""
    return model.dict()


def _format_mappings_for_storage(mappings: dict[str, str | None]) -> str:
    """将 header->field_key 映射编码为 JSON 列表。

    输出格式：[
        {"header": "姓名", "field_key": "name"},
        {"header": "手机号", "field_key": "mobile"},
    ]
    """
    items: list[dict[str, str | None]] = []
    for header, field_key in mappings.items():
        items.append({"header": header, "field_key": field_key})
    return json.dumps(items, ensure_ascii=False)


def _parse_stored_mappings(header_row_json: str) -> list[dict[str, str | None]]:
    """将存储的 JSON 字符串解析为映射列表。"""
    if not header_row_json or header_row_json == "[]":
        return []
    try:
        data = json.loads(header_row_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        # 旧格式：纯字符串列表 => 返回空映射
        if data and isinstance(data[0], str):
            return []
        # 新格式：对象列表
        return [{"header": item["header"], "field_key": item.get("field_key")} for item in data]
    return []


def save_mapping(
    db: DBSession,
    batch_id: int,
    mappings: dict[str, str | None],
    operator: str,
) -> dict:
    """保存列映射到批次记录。

    将 mappings 编码为 JSON 存入 batch.header_row；
    可选择将未知映射创建为用户列别名（当 mappings 中的 field_key 不在
    DEFAULT_FIELD_DEFINITIONS 中时自动创建 RosterColumnAlias）。

    Parameters
    ----------
    db : DBSession
    batch_id : int
    mappings : dict[str, str | None]
        header -> field_key（None 表示跳过该列）。
    operator : str
        操作人标识。

    Returns
    -------
    dict
        更新后的批次记录字典。
    """
    batch = db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"导入批次 {batch_id} 不存在")

    # 编码并存储
    batch.header_row = _format_mappings_for_storage(mappings)
    batch.updated_by = operator
    batch.updated_at = datetime.now()
    db.flush()

    # 为未知 field_key 自动创建列别名
    valid_keys = _field_key_set()
    for header, field_key in mappings.items():
        if field_key is None or field_key == "__skip__":
            continue
        if field_key in valid_keys:
            continue
        # 检查是否已存在
        norm_header = normalize_header(header)
        existing = (
            db.query(RosterColumnAlias)
            .filter(RosterColumnAlias.source_header_normalized == norm_header)
            .first()
        )
        if not existing:
            alias = RosterColumnAlias(
                source_header_normalized=norm_header,
                target_field_key=field_key,
                enabled=True,
                created_by=operator,
            )
            db.add(alias)

    return _to_dict(batch)


def get_mapping_for_batch(db: DBSession, batch_id: int) -> dict:
    """返回指定批次的列映射信息。"""
    batch = db.query(RosterImportBatch).filter(RosterImportBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"导入批次 {batch_id} 不存在")

    stored = _parse_stored_mappings(batch.header_row)

    # 构建 header -> field_key 字典
    mapping_dict: dict[str, str | None] = {}
    for item in stored:
        header = item["header"]
        field_key = item.get("field_key")
        if header not in mapping_dict:
            mapping_dict[header] = field_key

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "mappings": mapping_dict,
        "mapping_list": stored,
        "total_columns": len(stored),
        "mapped_count": sum(1 for m in stored if m.get("field_key") is not None),
    }


# ─── 列别名管理 ───────────────────────────────────────────────────────────────


def create_column_alias(db: DBSession, data: dict) -> dict:
    """创建列别名记录。

    Parameters
    ----------
    db : DBSession
    data : dict
        必填字段：source_header（原始表头）、target_field_key（目标字段键）。
        可选字段：enabled（默认 True）、created_by。

    Returns
    -------
    dict

    Raises
    ------
    Conflict
        当 source_header 对应的标准化值已存在时。
    """
    source_header = data.get("source_header", "").strip()
    if not source_header:
        raise ValueError("source_header 不能为空")
    target_field_key = data.get("target_field_key", "").strip()
    if not target_field_key:
        raise ValueError("target_field_key 不能为空")

    normalized = normalize_header(source_header)

    existing = (
        db.query(RosterColumnAlias)
        .filter(RosterColumnAlias.source_header_normalized == normalized)
        .first()
    )
    if existing:
        raise Conflict(f"列别名已存在：{source_header}（标准化：{normalized}）")

    enabled = data.get("enabled", True)
    created_by = data.get("created_by", "")

    alias = RosterColumnAlias(
        source_header_normalized=normalized,
        target_field_key=target_field_key,
        enabled=enabled,
        created_by=created_by,
    )
    db.add(alias)
    db.flush()

    return _to_dict(alias)


def list_column_aliases(db: DBSession) -> list[dict]:
    """列出所有列别名。"""
    aliases = db.query(RosterColumnAlias).order_by(RosterColumnAlias.id).all()
    return _to_dict_list(aliases)


# ─── 值别名管理 ───────────────────────────────────────────────────────────────


def create_value_alias(db: DBSession, data: dict) -> dict:
    """创建值别名记录。

    将 source_value 标准化后与 field_key 组成唯一约束。

    Parameters
    ----------
    db : DBSession
    data : dict
        必填字段：field_key、source_value（原文值）、target_value（目标值）。
        可选字段：created_by。

    Returns
    -------
    dict

    Raises
    ------
    Conflict
        当 (field_key, source_value 标准化后) 已存在时。
    """
    field_key = data.get("field_key", "").strip()
    if not field_key:
        raise ValueError("field_key 不能为空")
    source_value = data.get("source_value", "").strip()
    if not source_value:
        raise ValueError("source_value 不能为空")
    target_value = data.get("target_value", "").strip()
    if not target_value:
        raise ValueError("target_value 不能为空")

    source_normalized = normalize_value(source_value)

    existing = (
        db.query(RosterValueAlias)
        .filter(
            RosterValueAlias.field_key == field_key,
            RosterValueAlias.source_value_normalized == source_normalized,
        )
        .first()
    )
    if existing:
        raise Conflict(
            f"值别名已存在：field_key={field_key}, source_value={source_value}"
        )

    created_by = data.get("created_by", "")

    alias = RosterValueAlias(
        field_key=field_key,
        source_value_normalized=source_normalized,
        target_value=target_value,
        created_by=created_by,
    )
    db.add(alias)
    db.flush()

    return _to_dict(alias)


def list_value_aliases(db: DBSession, field_key: str | None = None) -> list[dict]:
    """列出值别名，可按 field_key 过滤。"""
    query = db.query(RosterValueAlias)
    if field_key:
        query = query.filter(RosterValueAlias.field_key == field_key)
    aliases = query.order_by(RosterValueAlias.field_key, RosterValueAlias.id).all()
    return _to_dict_list(aliases)


def resolve_value_alias(
    db: DBSession, field_key: str, source_value: str
) -> str | None:
    """查找值别名，返回标准化后的目标值。

    先精确匹配标准化后的 source_value；找不到则返回 None。

    Parameters
    ----------
    db : DBSession
    field_key : str
    source_value : str

    Returns
    -------
    str | None
        目标值（若存在别名），否则 None。
    """
    normalized = normalize_value(source_value)
    if not normalized:
        return None

    alias = (
        db.query(RosterValueAlias)
        .filter(
            RosterValueAlias.field_key == field_key,
            RosterValueAlias.source_value_normalized == normalized,
        )
        .first()
    )
    if alias:
        return alias.target_value
    return None


# ─── 组织参考数据 ─────────────────────────────────────────────────────────────


def get_org_references(
    db: DBSession, ref_type: str | None = None
) -> list[dict]:
    """获取组织参考数据（部门、岗位、分队等）。

    Parameters
    ----------
    db : DBSession
    ref_type : str | None
        筛选类型：DEPARTMENT / POSITION / TEAM；不传则返回全部。

    Returns
    -------
    list[dict]
    """
    query = db.query(OrganizationReference).filter(OrganizationReference.enabled == True)
    if ref_type:
        query = query.filter(OrganizationReference.reference_type == ref_type.upper())
    refs = query.order_by(OrganizationReference.reference_type, OrganizationReference.name).all()
    return _to_dict_list(refs)


# ─── 辅助工具 ─────────────────────────────────────────────────────────────────


def _to_dict_list(models: list) -> list[dict[str, Any]]:
    """将模型实例列表转为字典列表。"""
    return [m.dict() for m in models]

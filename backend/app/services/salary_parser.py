"""薪酬文本解析服务。

将花名册/简历中的中文薪资描述文本解析为结构化数据。
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional


def parse_salary_text(text: str | None) -> dict[str, Any]:
    """解析中文薪资描述文本，返回结构化薪资字典。

    支持的格式示例：
    - "试用期7000，转正8000"   -> probation=7000, regular=8000, MONTHLY
    - "7000（含30%绩效）"       -> base=7000, ratio=0.3, MONTHLY
    - "2000+提成"               -> base=2000, commission="提成", MIXED
    - "150/天"                  -> daily=150, DAILY
    - "5000"                    -> base=5000, MONTHLY
    - "面议" / None / ""        -> UNKNOWN

    所有货币值使用 Decimal 以避免浮点数精度问题。
    """
    result: dict[str, Any] = {
        "raw_salary_text": text or "",
        "salary_type": "UNKNOWN",
        "base_salary": None,
        "probation_salary": None,
        "regular_salary": None,
        "daily_rate": None,
        "performance_amount": None,
        "performance_ratio": None,
        "commission_text": None,
        "other_text": None,
    }

    if not text:
        return result

    text = text.strip()
    if not text:
        return result

    result["raw_salary_text"] = text
    has_structured = False

    # ------------------------------------------------------------------
    # 1. 日薪模式: "150/天" / "200/日"
    # ------------------------------------------------------------------
    daily_match = re.search(r"(\d+(?:\.\d+)?)\s*/(?:天|日)", text)
    if daily_match:
        result["daily_rate"] = Decimal(daily_match.group(1))
        result["salary_type"] = "DAILY"
        return result

    # ------------------------------------------------------------------
    # 2. 试用期/转正模式: "试用期7000，转正8000"
    #    需要 "试用" 和 "转正" 同时出现
    # ------------------------------------------------------------------
    if "试用" in text and "转正" in text:
        probation_nums = _extract_numbers_around_keyword(text, "试用")
        regular_nums = _extract_numbers_around_keyword(text, "转正")
        if probation_nums:
            result["probation_salary"] = probation_nums[0]
            has_structured = True
        if regular_nums:
            result["regular_salary"] = regular_nums[0]
            has_structured = True

    # ------------------------------------------------------------------
    # 3. 提成/绩效模式: "2000+提成" / "3000+绩效"
    # ------------------------------------------------------------------
    if "+" in text and any(kw in text for kw in ["提成", "绩效"]):
        parts = text.split("+", 1)
        before_plus = parts[0].strip()
        after_plus = parts[1].strip()

        base_num = _extract_number(before_plus)
        if base_num and result["base_salary"] is None:
            result["base_salary"] = base_num

        # 移除 "+" 后的纯数字/百分比前缀，提取文本描述
        clean_after = re.sub(r"[\d.]+%?", "", after_plus).strip()
        result["commission_text"] = clean_after or after_plus
        has_structured = True

    # ------------------------------------------------------------------
    # 4. 绩效比例: "30%" / "30％" / "7000（含30%绩效）"
    # ------------------------------------------------------------------
    pct = _extract_percentage(text)
    if pct is not None:
        result["performance_ratio"] = pct
        has_structured = True
        # 尝试从百分比之前的文本提取底薪
        if result["base_salary"] is None:
            pct_match = re.search(r"\d+(?:\.\d+)?\s*[%％]", text)
            if pct_match:
                before_pct = text[: pct_match.start()]
                base_num = _extract_number(before_pct)
                if base_num:
                    result["base_salary"] = base_num

    # ------------------------------------------------------------------
    # 5. 纯数字: "5000"
    # ------------------------------------------------------------------
    if not has_structured:
        single_num = _extract_number(text)
        if single_num is not None:
            result["base_salary"] = single_num
            has_structured = True

    # ------------------------------------------------------------------
    # 确定 salary_type
    # ------------------------------------------------------------------
    if has_structured:
        if result["commission_text"] is not None:
            result["salary_type"] = "MIXED"
        elif result["probation_salary"] is not None or result["regular_salary"] is not None:
            result["salary_type"] = "MONTHLY"
        elif result["base_salary"] is not None or result["performance_ratio"] is not None:
            result["salary_type"] = "MONTHLY"

    return result


def _extract_number(text: str) -> Decimal | None:
    """提取文本中第一个数字（整数或小数）。

    示例: "7000元" -> 7000, "8.5k" -> 8.5, "面议" -> None
    """
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return Decimal(match.group(1))
    return None


def _extract_percentage(text: str) -> Decimal | None:
    """提取百分比值（必须带 % 或 ％ 符号）。

    示例: "30%" -> 0.3, "30％" -> 0.3, "30" -> None
    """
    match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", text)
    if match:
        value = Decimal(match.group(1))
        return value / Decimal("100")
    return None


def _extract_numbers_around_keyword(text: str, keyword: str) -> list[Decimal]:
    """提取关键词附近出现的数字。

    示例:
    - "试用期7000，转正8000" 以 "试用" 为关键词 -> [Decimal('7000')]
    - "试用期7000，转正8000" 以 "转正" 为关键词 -> [Decimal('8000')]
    """
    pattern = re.compile(re.escape(keyword) + r".*?(\d+(?:\.\d+)?)")
    matches = pattern.findall(text)
    return [Decimal(m) for m in matches]

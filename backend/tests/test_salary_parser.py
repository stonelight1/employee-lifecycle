"""
薪资文本解析测试 -- SP-001 ~ SP-008
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.salary_parser import parse_salary_text


class TestProbationRegular:
    """SP-001 试用期/转正双关键词模式"""

    def test_typical_probation_regular(self):
        """'试用期7000，转正8000' -> probation=7000, regular=8000, MONTHLY"""
        result = parse_salary_text("试用期7000，转正8000")
        assert result["probation_salary"] == Decimal("7000")
        assert result["regular_salary"] == Decimal("8000")
        assert result["salary_type"] == "MONTHLY"

    def test_probation_regular_with_comma(self):
        """'试用期6500,转正8000' -> probation=6500, regular=8000, MONTHLY"""
        result = parse_salary_text("试用期6500,转正8000")
        assert result["probation_salary"] == Decimal("6500")
        assert result["regular_salary"] == Decimal("8000")
        assert result["salary_type"] == "MONTHLY"

    def test_probation_regular_no_space(self):
        """'试用期5500 转正7000' -> probation=5500, regular=7000, MONTHLY"""
        result = parse_salary_text("试用期5500 转正7000")
        assert result["probation_salary"] == Decimal("5500")
        assert result["regular_salary"] == Decimal("7000")
        assert result["salary_type"] == "MONTHLY"

    def test_only_probation_no_regular(self):
        """仅有试用期关键词,无转正 -> 提取 base_salary
        (代码要求'试用'和'转正'同时出现才进入双关键词分支)"""
        result = parse_salary_text("试用期6000")
        assert result["probation_salary"] is None
        assert result["regular_salary"] is None
        assert result["base_salary"] == Decimal("6000")
        assert result["salary_type"] == "MONTHLY"

    def test_only_regular_no_probation(self):
        """仅有转正关键词,无试用期 -> 提取 base_salary"""
        result = parse_salary_text("转正后8000")
        assert result["probation_salary"] is None
        assert result["regular_salary"] is None
        assert result["base_salary"] == Decimal("8000")
        assert result["salary_type"] == "MONTHLY"


class TestCommissionPattern:
    """SP-002 提成/绩效模式"""

    def test_salary_plus_commission(self):
        """'2000+提成' -> base=2000, commission='提成', MIXED"""
        result = parse_salary_text("2000+提成")
        assert result["base_salary"] == Decimal("2000")
        assert result["commission_text"] == "提成"
        assert result["salary_type"] == "MIXED"

    def test_salary_plus_performance(self):
        """'3000+绩效' -> base=3000, commission='绩效', MIXED"""
        result = parse_salary_text("3000+绩效")
        assert result["base_salary"] == Decimal("3000")
        assert result["commission_text"] == "绩效"
        assert result["salary_type"] == "MIXED"

    def test_large_salary_plus_commission(self):
        """'15000+提成' -> base=15000, commission='提成', MIXED"""
        result = parse_salary_text("15000+提成")
        assert result["base_salary"] == Decimal("15000")
        assert result["commission_text"] == "提成"
        assert result["salary_type"] == "MIXED"

    def test_salary_plus_detailed_commission(self):
        """'2000+销售提成' -> base=2000, commission='销售提成', MIXED"""
        result = parse_salary_text("2000+销售提成")
        assert result["base_salary"] == Decimal("2000")
        assert result["commission_text"] == "销售提成"
        assert result["salary_type"] == "MIXED"


class TestDailyRate:
    """SP-003 日薪模式"""

    def test_daily_rate_tian(self):
        """'150/天' -> daily=150, DAILY"""
        result = parse_salary_text("150/天")
        assert result["daily_rate"] == Decimal("150")
        assert result["salary_type"] == "DAILY"

    def test_daily_rate_ri(self):
        """'150/日' -> daily=150, DAILY"""
        result = parse_salary_text("150/日")
        assert result["daily_rate"] == Decimal("150")
        assert result["salary_type"] == "DAILY"

    def test_daily_rate_decimal(self):
        """'150.5/天' -> daily=150.5, DAILY"""
        result = parse_salary_text("150.5/天")
        assert result["daily_rate"] == Decimal("150.5")
        assert result["salary_type"] == "DAILY"

    def test_daily_rate_large_number(self):
        """'300/天' -> daily=300, DAILY"""
        result = parse_salary_text("300/天")
        assert result["daily_rate"] == Decimal("300")
        assert result["salary_type"] == "DAILY"

    def test_daily_rate_returns_immediately(self):
        """日薪模式提前返回,不提取其他字段"""
        result = parse_salary_text("200/天")
        assert result["base_salary"] is None
        assert result["probation_salary"] is None
        assert result["regular_salary"] is None


class TestPlainNumber:
    """SP-004 纯数字模式"""

    def test_plain_monthly(self):
        """'5000' -> base=5000, MONTHLY"""
        result = parse_salary_text("5000")
        assert result["base_salary"] == Decimal("5000")
        assert result["salary_type"] == "MONTHLY"

    def test_plain_large_number(self):
        """'25000' -> base=25000, MONTHLY"""
        result = parse_salary_text("25000")
        assert result["base_salary"] == Decimal("25000")
        assert result["salary_type"] == "MONTHLY"

    def test_plain_with_whitespace(self):
        """' 5000 ' -> base=5000, MONTHLY (去除首尾空格后仍在解析范围内)"""
        result = parse_salary_text(" 5000 ")
        assert result["base_salary"] == Decimal("5000")
        assert result["salary_type"] == "MONTHLY"

    def text_with_unit(self):
        """'7000元' -> base=7000, MONTHLY"""
        result = parse_salary_text("7000元")
        assert result["base_salary"] == Decimal("7000")
        assert result["salary_type"] == "MONTHLY"


class TestPerformanceRatio:
    """SP-005 含绩效比例模式"""

    def test_salary_with_performance_ratio(self):
        """'7000(含30%绩效)' -> base=7000, ratio=0.3, MONTHLY"""
        result = parse_salary_text("7000（含30%绩效）")
        assert result["base_salary"] == Decimal("7000")
        assert result["performance_ratio"] == Decimal("0.3")
        assert result["salary_type"] == "MONTHLY"

    def test_salary_with_percent_sign_fullwidth(self):
        """全角百分号: '8000(含20%绩效)' -> base=8000, ratio=0.2"""
        result = parse_salary_text("8000（含20％绩效）")
        assert result["base_salary"] == Decimal("8000")
        assert result["performance_ratio"] == Decimal("0.2")

    def test_performance_ratio_only(self):
        """'底薪+30%绩效' -> commission 分支优先, 绩效比例 0.3, 无 base (无前置数字)"""
        result = parse_salary_text("底薪+30%绩效")
        assert result["performance_ratio"] == Decimal("0.3")
        assert result["commission_text"] == "绩效"
        assert result["base_salary"] is None
        assert result["salary_type"] == "MIXED"


class TestUnknownOrEmpty:
    """SP-006 无法解析的输入"""

    def test_none_input(self):
        """None -> UNKNOWN"""
        result = parse_salary_text(None)
        assert result["salary_type"] == "UNKNOWN"
        assert result["base_salary"] is None

    def test_empty_string(self):
        """'' -> UNKNOWN"""
        result = parse_salary_text("")
        assert result["salary_type"] == "UNKNOWN"
        assert result["base_salary"] is None

    def test_whitespace_only(self):
        """仅空白 -> UNKNOWN (strip 后为空)"""
        result = parse_salary_text("   ")
        assert result["salary_type"] == "UNKNOWN"
        assert result["base_salary"] is None

    def test_mianyi(self):
        """'面议' -> UNKNOWN"""
        result = parse_salary_text("面议")
        assert result["salary_type"] == "UNKNOWN"
        assert result["base_salary"] is None

    def test_mianyi_variant(self):
        """'薪资面议' -> UNKNOWN"""
        result = parse_salary_text("薪资面议")
        assert result["salary_type"] == "UNKNOWN"

    def test_no_numbers(self):
        """纯文字无数字 -> UNKNOWN"""
        result = parse_salary_text("无")
        assert result["salary_type"] == "UNKNOWN"


class TestCombinedPatterns:
    """SP-007 多模式组合"""

    def test_probation_regular_with_performance(self):
        """试用期转正 + 绩效比例"""
        result = parse_salary_text("试用期6500，转正8000（含30%绩效）")
        assert result["probation_salary"] == Decimal("6500")
        assert result["regular_salary"] == Decimal("8000")
        assert result["performance_ratio"] == Decimal("0.3")
        assert result["base_salary"] == Decimal("6500")
        assert result["salary_type"] == "MONTHLY"

    def test_salary_plus_commission_with_space(self):
        """含空格的提成模式"""
        result = parse_salary_text("2000 + 提成")
        assert result["base_salary"] == Decimal("2000")
        assert result["commission_text"] == "提成"
        assert result["salary_type"] == "MIXED"


class TestResultStructure:
    """SP-008 返回结果结构校验"""

    def test_result_contains_all_keys(self):
        """所有必填键都存在"""
        result = parse_salary_text("5000")
        expected_keys = {
            "raw_salary_text", "salary_type", "base_salary",
            "probation_salary", "regular_salary", "daily_rate",
            "performance_amount", "performance_ratio",
            "commission_text", "other_text",
        }
        assert set(result.keys()) == expected_keys

    def test_raw_text_preserved(self):
        """raw_salary_text 保存原始输入"""
        result = parse_salary_text("试用期7000，转正8000")
        assert result["raw_salary_text"] == "试用期7000，转正8000"

    def test_decimal_type(self):
        """所有薪资值为 Decimal 类型"""
        result = parse_salary_text("5000")
        assert isinstance(result["base_salary"], Decimal)

    def test_salary_type_string(self):
        """salary_type 为字符串"""
        result = parse_salary_text("5000")
        assert isinstance(result["salary_type"], str)

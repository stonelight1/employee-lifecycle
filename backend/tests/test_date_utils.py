"""统一日期解析器测试。"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.date_utils import (
    EXCEL_DATE_EPOCH_1900,
    EXCEL_DATE_EPOCH_1904,
    normalize_text,
    parse_date_value,
    parse_optional_date,
)


class TestParseDateValue:
    """P0: 所有模块使用同一日期解析器。"""

    def test_date_object(self):
        """date 对象直接返回。"""
        d = date(2026, 7, 16)
        assert parse_date_value(d) == d

    def test_iso_dash(self):
        """2026-07-16 格式。"""
        assert parse_date_value("2026-07-16") == date(2026, 7, 16)

    def test_iso_slash(self):
        """2026/7/16 格式。"""
        assert parse_date_value("2026/7/16") == date(2026, 7, 16)

    def test_iso_dot(self):
        """2026.7.16 格式。"""
        assert parse_date_value("2026.7.16") == date(2026, 7, 16)

    def test_continuous_digits(self):
        """20260716 格式（8位连续数字）。"""
        assert parse_date_value("20260716") == date(2026, 7, 16)

    def test_chinese_date(self):
        """2026年7月16日 格式。"""
        assert parse_date_value("2026年7月16日") == date(2026, 7, 16)

    def test_chinese_date_padded(self):
        """2026年07月16日 格式。"""
        assert parse_date_value("2026年07月16日") == date(2026, 7, 16)

    def test_excel_serial_1900(self):
        """Excel 日期序列号（1900 系统）。"""
        # 2026-07-16 的 Excel 序列号
        target = date(2026, 7, 16)
        serial = (target - EXCEL_DATE_EPOCH_1900).days
        assert parse_date_value(serial) == target

    def test_excel_serial_1900_float(self):
        """Excel 日期序列号浮点数。"""
        target = date(2026, 7, 16)
        serial = float((target - EXCEL_DATE_EPOCH_1900).days)
        assert parse_date_value(serial) == target

    def test_none(self):
        """None → None。"""
        assert parse_date_value(None) is None

    def test_empty_string(self):
        """空字符串 → None。"""
        assert parse_date_value("") is None
        assert parse_date_value("   ") is None

    def test_invalid_date(self):
        """非法日期 → None。"""
        assert parse_date_value("not-a-date") is None
        assert parse_date_value("13月32日") is None
        assert parse_date_value("2026-13-01") is None

    def test_year_month_only(self):
        """仅有月日 → None（不猜测年份）。"""
        assert parse_date_value("7月16日") is None
        assert parse_date_value("07-16") is None

    def test_partial_month_day(self):
        """不完整的日期 → None。"""
        assert parse_date_value("16") is None
        assert parse_date_value("2026") is None


class TestParseOptionalDate:
    """parse_optional_date 同 parse_date_value 行为一致。"""

    def test_same_as_parse_date(self):
        """行为与 parse_date_value 一致。"""
        assert parse_optional_date("2026-07-16") == parse_date_value("2026-07-16")
        assert parse_optional_date(None) is None
        assert parse_optional_date("invalid") is None


class TestNormalizeText:
    """文本清洗测试。"""

    def test_strip(self):
        """去除首尾空格。"""
        assert normalize_text("  合作  ") == "合作"

    def test_fullwidth(self):
        """全角转半角。"""
        assert normalize_text("ＡＢＣ") == "ABC"
        assert normalize_text("１２３") == "123"

    def test_collapse_whitespace(self):
        """连续空白压缩。"""
        assert normalize_text("合  作") == "合 作"

    def test_newline_removed(self):
        """去掉单元格换行。"""
        assert normalize_text("合作\n") == "合作"
        assert normalize_text("合\n作") == "合 作"

    def test_mixed(self):
        """混合清洗。"""
        result = normalize_text("  合作　公司\n测试  ")
        assert result == "合作 公司 测试"

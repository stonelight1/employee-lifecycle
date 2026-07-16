"""合作地区检测测试。"""
from __future__ import annotations

import pytest

from app.services.roster_cooperation import is_cooperation_region


class TestCooperationRegion:
    """P0: 地区为"合作"时整行跳过。"""

    def test_exact_cooperation(self):
        """精确"合作"地区 → 跳过。"""
        assert is_cooperation_region({"work_city": "合作"}) is True

    def test_empty(self):
        """空地区 → 不跳过。"""
        assert is_cooperation_region({"work_city": ""}) is False
        assert is_cooperation_region({"work_city": None}) is False

    def test_normal_city(self):
        """正常城市 → 不跳过。"""
        assert is_cooperation_region({"work_city": "武汉"}) is False
        assert is_cooperation_region({"work_city": "北京"}) is False
        assert is_cooperation_region({"work_city": "上海"}) is False
        assert is_cooperation_region({"work_city": "深圳"}) is False

    def test_leading_trailing_spaces(self):
        """前后空格 → 正常跳过。"""
        assert is_cooperation_region({"work_city": " 合作"}) is True
        assert is_cooperation_region({"work_city": "合作 "}) is True
        assert is_cooperation_region({"work_city": " 合作 "}) is True

    def test_fullwidth_spaces(self):
        """全角空格 → 正常跳过。"""
        assert is_cooperation_region({"work_city": "　合作　"}) is True
        assert is_cooperation_region({"work_city": "　合作"}) is True

    def test_not_cooperation(self):
        """非精确值 → 不跳过。"""
        assert is_cooperation_region({"work_city": "合作公司"}) is False
        assert is_cooperation_region({"work_city": "合作方"}) is False
        assert is_cooperation_region({"work_city": "合作模式"}) is False
        assert is_cooperation_region({"work_city": "渠道合作"}) is False
        assert is_cooperation_region({"work_city": "战略合作"}) is False
        assert is_cooperation_region({"work_city": "武汉合作"}) is False

    def test_mixed_case_with_spaces(self):
        """混合空格和特殊字符 → 精确等于合作才跳过。"""
        assert is_cooperation_region({"work_city": " 合 作 "}) is False  # 中间有空格
        assert is_cooperation_region({"work_city": "合作\n"}) is True  # 换行符
        assert is_cooperation_region({"work_city": "合作\t"}) is True  # Tab

    def test_missing_key(self):
        """缺少 work_city 键 → 不跳过。"""
        assert is_cooperation_region({}) is False
        assert is_cooperation_region({"name": "张三"}) is False

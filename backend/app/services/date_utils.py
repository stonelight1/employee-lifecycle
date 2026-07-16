"""统一日期解析工具。

所有花名册导入模块（Excel解析、字段映射、行标准化、预览、正式提交、HR确认）
必须调用此模块的方法，禁止各自维护独立的日期解析逻辑。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

# ============================================================
# Excel 日期序列号常量
# ============================================================

EXCEL_DATE_EPOCH_1900 = date(1899, 12, 30)
"""Excel 1900 日期系统纪元（含闰年 Bug 补偿）。"""

EXCEL_DATE_EPOCH_1904 = date(1904, 1, 1)
"""Excel 1904 日期系统纪元（Mac 版本）。"""

_MAX_DATE_SERIAL = 2958465
"""Excel 最大有效日期序列号（9999-12-31）。"""

# ============================================================
# 公共 API
# ============================================================

# 支持的日期字符串格式（按优先级排列）
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
    "%Y-%m-%d",
]

# 8601 长度格式日期正则
_RE_YYYY_MM_DD = re.compile(r"^\s*(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*$")
_RE_YYYYMMDD = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})\s*$")
_RE_CHINESE_DATE = re.compile(r"^\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*$")


def parse_date_value(value: Any, epoch: date | None = None) -> date | None:
    """解析任意类型的日期值为 date 对象。

    支持：
    - datetime / date 对象
    - Excel 日期序列号（int / float）
    - 字符串：2026-07-16, 2026/7/16, 2026.7.16, 20260716, 2026年7月16日

    Args:
        value: 待解析的日期值。
        epoch: Excel 日期系统纪元。None 时使用 1900 系统。

    Returns:
        date | None: 解析成功返回 date，否则返回 None。不猜测月份-日期格式。
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return _parse_date_string(value.strip())

    if isinstance(value, (int, float)):
        return _excel_serial_to_date(value, epoch or EXCEL_DATE_EPOCH_1900)

    return None


def parse_optional_date(value: Any) -> date | None:
    """同 parse_date_value，返回 None 而非异常。"""
    try:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            return parse_date_value(text)
        if isinstance(value, (int, float)):
            return _excel_serial_to_date(value, EXCEL_DATE_EPOCH_1900)
        return None
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_text(text: Any) -> str:
    """清洗文本：去空格、全角转半角、压缩连续空白、去掉换行。

    Args:
        text: 原始文本。

    Returns:
        str: 清洗后的文本。
    """
    if text is None:
        return ""
    s = str(text).strip()
    s = _fullwidth_to_halfwidth(s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\n", "").replace("\r", "").replace("\t", " ")
    return s


# ============================================================
# 内部实现
# ============================================================


def _parse_date_string(date_str: str) -> date | None:
    """解析日期字符串。

    支持的格式（按优先级）：
    1. 2026年7月16日
    2. 2026-07-16 / 2026/7/16 / 2026.7.16
    3. 20260716

    缺少年份的格式（如 7月16日）返回 None。
    """
    if not date_str:
        return None

    # "2026年7月16日" / "2026年07月16日"
    m = _RE_CHINESE_DATE.match(date_str)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # "2026-07-16" / "2026/7/16" / "2026.7.16"
    m = _RE_YYYY_MM_DD.match(date_str)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    # "20260716"（8 位连续数字）
    m = _RE_YYYYMMDD.match(date_str)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    # 仅有月日无年份 → 不明确，返回 None
    return None


def _excel_serial_to_date(serial: int | float, epoch: date) -> date | None:
    """将 Excel 日期序列号转换为 date 对象。"""
    if isinstance(serial, float) and serial != int(serial):
        serial = int(serial)
    if serial < 1 or serial > _MAX_DATE_SERIAL:
        return None
    try:
        return epoch + timedelta(days=int(serial))
    except (OverflowError, ValueError):
        return None


def _fullwidth_to_halfwidth(text: str) -> str:
    """全角字母、数字、空格→半角。"""
    result: list[str] = []
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(" ")
        else:
            result.append(char)
    return "".join(result)

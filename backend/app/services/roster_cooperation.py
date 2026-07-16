"""合作地区检测 —— 统一判断逻辑，所有模块使用同一方法。"""

from __future__ import annotations

from typing import Any

from .date_utils import normalize_text


def is_cooperation_region(normalized_data: dict) -> bool:
    """判断标准化后的行数据是否属于"合作"地区。

    判断前统一处理（normalize_text）：
    - 去掉首尾空格
    - 全角转半角
    - 连续空白压缩
    - 去掉单元格换行

    标准化后的值严格等于"合作"才返回 True。

    Args:
        normalized_data: 标准化后的行数据 dict，需包含 work_city 字段。

    Returns:
        bool: 如果地区严格等于"合作"返回 True。
    """
    region = normalize_text(normalized_data.get("work_city"))
    return region == "合作"

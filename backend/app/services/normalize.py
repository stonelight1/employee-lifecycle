"""姓名标准化工具。"""

from __future__ import annotations

import re


def normalize_name(name: str) -> str:
    """
    姓名确定性标准化。

    规则（与 docs/01-domain-rules.md 2.2 节一致）：
    1. 去除首尾空格。
    2. 将全角空格（U+3000）统一为半角空格。
    3. 将连续空白字符压缩为单个空格。

    不得进行拼音、模糊相似度或同音自动匹配。
    """
    if not name:
        return ""

    # 去除首尾空格
    name = name.strip()
    # 统一全角空格
    name = name.replace("　", " ")
    # 连续空白压缩为单个空格
    name = re.sub(r"\s+", " ", name)

    return name

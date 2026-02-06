"""輸出正規化工具。

在比較 golden output 與 refactored output 之前，
清洗已知的非確定性欄位（時間戳、UUID、隨機數等），
減少誤判 fail。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# 預設正規化規則：pattern → 替換值
_DEFAULT_RULES: list[tuple[str, str]] = [
    # ISO 8601 時間戳
    (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.\d]*Z?", "<TIMESTAMP>"),
    # Unix timestamp（10 或 13 位數字）
    (r"\b\d{10,13}\b", "<UNIX_TS>"),
    # UUID v4
    (r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", "<UUID>"),
    # 32 字元 hex（常見於 uuid4().hex）
    (r"\b[0-9a-f]{32}\b", "<HEX32>"),
]


@dataclass
class OutputNormalizer:
    """可插拔的輸出正規化器。

    透過正規表達式規則清洗非確定性欄位。
    可透過 ``add_rule`` 動態新增規則。

    Attributes:
        rules: (pattern, replacement) 的規則清單。
    """

    rules: list[tuple[re.Pattern[str], str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """初始化預設規則。"""
        if not self.rules:
            self.rules = [(re.compile(p, re.IGNORECASE), r) for p, r in _DEFAULT_RULES]

    def add_rule(self, pattern: str, replacement: str) -> None:
        """新增自訂正規化規則。

        Args:
            pattern: 正規表達式。
            replacement: 替換字串。
        """
        self.rules.append((re.compile(pattern), replacement))

    def normalize(self, output: Any) -> str:
        """正規化輸出為可比較的字串。

        若輸入為 dict/list，先做 key 排序的 JSON 序列化；
        再逐條套用 regex 規則。

        Args:
            output: 原始輸出（可為 str、dict、list 或其他）。

        Returns:
            正規化後的字串。
        """
        if output is None:
            return ""

        if isinstance(output, (dict, list)):
            text = json.dumps(output, sort_keys=True, ensure_ascii=False)
        else:
            text = str(output)

        for pattern, replacement in self.rules:
            text = pattern.sub(replacement, text)

        return text

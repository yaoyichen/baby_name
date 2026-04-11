"""
filters/tone_filter.py — 平仄规则过滤器

规则：三字名要求满足 平—仄—平 的声调模式。
  - 位置1（姓氏）：平声（声调1或2）
  - 位置2（名1）：仄声（声调3或4）
  - 位置3（名2）：平声（声调1或2）

对于姚姓（yáo，声调2）：
  - 姓氏已是平声，满足位置1要求
  - 只需校验 名1 为仄声、名2 为平声

由于 generator.py 已按声调分池（仄声池×平声池）生成组合，
此过滤器主要用作后备校验，以及支持不按分池方式调用时的兜底保障。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import NameFilter

if TYPE_CHECKING:
    from char_pool import CharAttr

PING_TONES = frozenset({1, 2})   # 平声：阴平、阳平
ZE_TONES = frozenset({3, 4})     # 仄声：上声、去声


class ToneFilter(NameFilter):
    """
    平仄模式过滤器。

    支持自定义期望模式，默认为 平仄平（适合姚姓）。

    Args:
        pattern: 长度为3的声调类型列表，'ping' 表示平声，'ze' 表示仄声。
                 默认 ['ping', 'ze', 'ping']。

    Examples:
        ToneFilter()                           # 默认：平仄平
        ToneFilter(['ze', 'ping', 'ze'])       # 仄平仄
        ToneFilter(['ping', 'ping', 'ze'])     # 平平仄
    """

    def __init__(self, pattern: list[str] | None = None) -> None:
        if pattern is None:
            pattern = ['ping', 'ze', 'ping']
        if len(pattern) != 3:
            raise ValueError("pattern 必须包含3个元素，对应三字名的每一个字")
        for p in pattern:
            if p not in ('ping', 'ze'):
                raise ValueError(f"pattern 元素必须为 'ping' 或 'ze'，收到: {p!r}")
        self._pattern = pattern

    @property
    def description(self) -> str:
        labels = {'ping': '平', 'ze': '仄'}
        pattern_str = '—'.join(labels[p] for p in self._pattern)
        return f"平仄规则（{pattern_str}）"

    def _matches(self, tone: int, expected: str) -> bool:
        if expected == 'ping':
            return tone in PING_TONES
        return tone in ZE_TONES

    def check(
        self,
        surname_attr: "CharAttr",
        name1_attr: "CharAttr",
        name2_attr: "CharAttr",
    ) -> bool:
        """
        校验三字名是否满足平仄模式。

        Returns:
            True  → 声调模式符合要求
            False → 不符合，过滤掉
        """
        attrs = [surname_attr, name1_attr, name2_attr]
        return all(
            self._matches(attr.tone, expected)
            for attr, expected in zip(attrs, self._pattern)
        )

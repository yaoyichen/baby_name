"""
filters/openness_filter.py — 开口度规则过滤器

规则：避免三字名中所有字均为小开口（局促音）。
小开口字发音时上下颌接近，共鸣空间小，远距离呼唤时声音传不出去。

四呼分类：
  - 大开口（开口呼）：韵母不以 i/u/ü 开头，如 a, o, e, ao, an, ang 等
  - 小开口：
      齐齿呼：韵母以 i 开头，如 i, in, ing, ia, ie 等
      合口呼：韵母以 u 开头，如 u, un, uo, ua 等
      撮口呼：韵母以 ü(v) 开头，如 ü, ün, üe 等

注：姚（yáo）韵母为 'ao'，属大开口，因此姚姓名字不会触发默认规则。
    该过滤器对任意姓氏均有效，保留以确保框架完整可复用。

两种模式：
  - strict=False（默认）：三字全为小开口才过滤
  - strict=True：要求名字的后两字中至少一个为大开口（更严格）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import NameFilter

if TYPE_CHECKING:
    from char_pool import CharAttr


class OpennessFilter(NameFilter):
    """
    开口度过滤器。

    Args:
        strict: 是否启用严格模式。
            False（默认）→ 拒绝三字全为小开口的名字
            True          → 额外要求：名1和名2中至少一个为大开口
    """

    def __init__(self, strict: bool = False) -> None:
        self._strict = strict

    @property
    def description(self) -> str:
        if self._strict:
            return "开口度规则（严格：名字后两字至少一个大开口）"
        return "开口度规则（三字全小开口则拒绝）"

    def check(
        self,
        surname_attr: "CharAttr",
        name1_attr: "CharAttr",
        name2_attr: "CharAttr",
    ) -> bool:
        """
        校验三字名的开口度是否合格。

        Returns:
            True  → 开口度符合要求
            False → 不符合，过滤掉
        """
        if self._strict:
            # 严格模式：名1 或 名2 中至少一个必须是大开口
            return (
                name1_attr.openness == 'large'
                or name2_attr.openness == 'large'
            )

        # 宽松模式（默认）：仅当三字全部小开口时才拒绝
        all_small = (
            surname_attr.openness == 'small'
            and name1_attr.openness == 'small'
            and name2_attr.openness == 'small'
        )
        return not all_small

"""
filters/base.py — 过滤器抽象基类

所有过滤器均继承 NameFilter，实现 check() 方法。
生成器通过统一接口调用过滤器链，无需感知具体规则。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from char_pool import CharAttr


class NameFilter(ABC):
    """
    名字过滤器抽象基类。

    Usage:
        class MyFilter(NameFilter):
            @property
            def description(self) -> str:
                return "我的规则说明"

            def check(self, surname_attr, name1_attr, name2_attr) -> bool:
                # 返回 True 表示通过，False 表示被过滤掉
                ...
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """过滤器的简短描述，用于统计报告"""

    @abstractmethod
    def check(
        self,
        surname_attr: "CharAttr",
        name1_attr: "CharAttr",
        name2_attr: "CharAttr",
    ) -> bool:
        """
        判断一个三字名是否通过该过滤器。

        Args:
            surname_attr: 姓氏的语音属性
            name1_attr:   名字第二字（名1）的语音属性
            name2_attr:   名字第三字（名2）的语音属性

        Returns:
            True  → 通过，保留该名字
            False → 不通过，过滤掉该名字
        """

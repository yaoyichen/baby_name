"""
filters — 名字过滤器模块

每个过滤器实现 NameFilter 抽象基类，可独立添加/移除。

当前过滤器：
  - ToneFilter        平仄规则（如：平仄平）
  - OpennessFilter    开口度规则（避免三字全小开口）

后续扩展示例：
  - WuXingFilter      五行/八字规则
  - StrokeFilter      笔画均衡规则
  - RadicalFilter     偏旁多样性规则
"""

from .base import NameFilter
from .openness_filter import OpennessFilter
from .tone_filter import ToneFilter

__all__ = ["NameFilter", "ToneFilter", "OpennessFilter"]

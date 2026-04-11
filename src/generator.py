"""
generator.py — 名字生成器

流程：
  1. 接收字符池（CharPool）和过滤器列表
  2. 通过 仄声池 × 平声池 的笛卡尔积生成候选组合（已满足平仄平要求）
  3. 去除含重复字的组合（名1 == 名2，或名字字与姓氏相同）
  4. 依次应用额外过滤器（如开口度、五行等）
  5. 每阶段打印统计报告
  6. 返回候选名单，并可选写出到 CSV

设计考量：
  - 使用生成器（yield）流式处理，避免一次性加载数百万条记录到内存
  - CSV 流式写入，内存峰值仅取决于批次大小
"""

from __future__ import annotations

import csv
import itertools
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from char_pool import CharAttr, CharPool, load_chars_from_csv
from filters.base import NameFilter


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

@dataclass
class NameCandidate:
    """一个候选名字及其完整属性"""
    name: str            # 完整三字名，如 '姚溯渊'
    surname_attr: CharAttr
    name1_attr: CharAttr
    name2_attr: CharAttr

    @property
    def pinyin_str(self) -> str:
        return (f"{self.surname_attr.pinyin} "
                f"{self.name1_attr.pinyin} "
                f"{self.name2_attr.pinyin}")

    @property
    def wuxing_str(self) -> str:
        """三字五行组合，如 '土-木-水'"""
        def wx(attr: CharAttr) -> str:
            return attr.wuxing or "?"
        return f"{wx(self.surname_attr)}-{wx(self.name1_attr)}-{wx(self.name2_attr)}"

    def to_csv_row(self) -> dict:
        return {
            # 基本信息
            "name": self.name,
            "char2": self.name1_attr.char,
            "char3": self.name2_attr.char,
            # 拼音
            "pinyin_full": self.pinyin_str,
            "pinyin1": self.surname_attr.pinyin,
            "pinyin2": self.name1_attr.pinyin,
            "pinyin3": self.name2_attr.pinyin,
            # 声调
            "tone1": self.surname_attr.tone,
            "tone2": self.name1_attr.tone,
            "tone3": self.name2_attr.tone,
            # 韵母 & 开口度
            "final1": self.surname_attr.final,
            "final2": self.name1_attr.final,
            "final3": self.name2_attr.final,
            "openness1": self.surname_attr.openness,
            "openness2": self.name1_attr.openness,
            "openness3": self.name2_attr.openness,
            # 笔画
            "strokes1": self.surname_attr.stroke_count,
            "strokes2": self.name1_attr.stroke_count,
            "strokes3": self.name2_attr.stroke_count,
            # 五行
            "wuxing1": self.surname_attr.wuxing or "",
            "wuxing2": self.name1_attr.wuxing or "",
            "wuxing3": self.name2_attr.wuxing or "",
            "wuxing_combo": self.wuxing_str,
            # 部首
            "radical2": self.name1_attr.radical,
            "radical3": self.name2_attr.radical,
        }


# ──────────────────────────────────────────────
# 核心生成器
# ──────────────────────────────────────────────

def _generate_raw(
    surname_attr: CharAttr,
    ze_pool: list[CharAttr],
    ping_pool: list[CharAttr],
) -> Iterator[NameCandidate]:
    """
    生成仄声池 × 平声池 的笛卡尔积（已满足平仄平格式）。
    过滤掉含重复字的组合。
    """
    surname_char = surname_attr.char
    for name1, name2 in itertools.product(ze_pool, ping_pool):
        # 避免名字中出现重复字
        if name1.char == name2.char:
            continue
        # 名字中不重复姓氏（char_pool 构建时已排除，此处为双重保障）
        if name1.char == surname_char or name2.char == surname_char:
            continue
        yield NameCandidate(
            name=f"{surname_char}{name1.char}{name2.char}",
            surname_attr=surname_attr,
            name1_attr=name1,
            name2_attr=name2,
        )


# ──────────────────────────────────────────────
# 流水线执行
# ──────────────────────────────────────────────

def run_pipeline(
    surname: str,
    pool: CharPool,
    filters: list[NameFilter],
    output_csv: Path | None = None,
    preview_count: int = 10,
    verbose: bool = True,
) -> list[NameCandidate]:
    """
    执行完整的名字生成和过滤流水线。

    Args:
        surname:       姓氏，如 '姚'
        pool:          由 build_char_pool 返回的字符池
        filters:       过滤器列表，按顺序应用
        output_csv:    CSV 输出路径，None 则不输出文件
        preview_count: 控制台预览的名字数量
        verbose:       是否打印详细统计

    Returns:
        通过所有过滤器的 NameCandidate 列表
    """
    # 从已构建的字符池中查姓氏属性（避免重复读 CSV）
    # 姓氏在 build_char_pool 时被排除出 pool，需单独从全量 CSV 里查
    _all = load_chars_from_csv()
    surname_attr = _all.get(surname)
    if surname_attr is None:
        print(f"错误：'{surname}' 是多音字或在数据中找不到，请检查输入。", file=sys.stderr)
        return []

    if verbose:
        print(f"\n  姓氏：{surname}（{surname_attr.pinyin}，"
              f"声调{surname_attr.tone}，韵母'{surname_attr.final}'，"
              f"开口度：{surname_attr.openness}）")

    # 阶段1：生成原始笛卡尔积
    t0 = time.perf_counter()
    raw_count = 0
    candidates: list[NameCandidate] = []

    # 先统计总数（用于显示，避免两次遍历占内存，直接流式处理）
    raw_stream = _generate_raw(surname_attr, pool.ze_pool, pool.ping_pool)

    if verbose:
        expected_raw = len(pool.ze_pool) * len(pool.ping_pool)
        print(f"\n[阶段1] 笛卡尔积生成（仄声池×平声池）")
        print(f"  预计组合数（含重复）：{expected_raw:,}")

    # 应用所有过滤器（流式处理）
    filter_stats: dict[str, int] = {}

    for candidate in raw_stream:
        raw_count += 1

        passed = True
        for f in filters:
            if not f.check(
                candidate.surname_attr,
                candidate.name1_attr,
                candidate.name2_attr,
            ):
                filter_stats[f.description] = filter_stats.get(f.description, 0) + 1
                passed = False
                break

        if passed:
            candidates.append(candidate)

    elapsed = time.perf_counter() - t0

    if verbose:
        print(f"  实际组合数（去重复字后）：{raw_count:,}")
        print(f"\n[阶段2] 过滤器应用结果")
        if not filters:
            print("  （未配置任何过滤器）")
        for f in filters:
            rejected = filter_stats.get(f.description, 0)
            print(f"  {f.description}：过滤 {rejected:,} 条")
        print(f"\n  最终候选数：{len(candidates):,}")
        print(f"  耗时：{elapsed:.1f} 秒")

    # 预览输出
    if verbose and candidates:
        print(f"\n[预览] 前 {min(preview_count, len(candidates))} 个候选名字：")
        print(f"  {'序':>3}  {'名字':<5} {'拼音':<18} {'声调':<6} {'五行':<10} {'笔画'}")
        print(f"  {'-'*3}  {'-'*5} {'-'*18} {'-'*6} {'-'*10} {'-'*8}")
        for i, c in enumerate(candidates[:preview_count]):
            strokes = (f"{c.surname_attr.stroke_count}+"
                       f"{c.name1_attr.stroke_count}+"
                       f"{c.name2_attr.stroke_count}")
            print(f"  {i+1:3d}. {c.name:<5} {c.pinyin_str:<18} "
                  f"{c.surname_attr.tone}/{c.name1_attr.tone}/{c.name2_attr.tone}    "
                  f"{c.wuxing_str:<10} {strokes}")

    # CSV 输出
    if output_csv is not None:
        _write_csv(candidates, output_csv, verbose=verbose)

    return candidates


def _write_csv(
    candidates: list[NameCandidate],
    path: Path,
    verbose: bool = True,
) -> None:
    """将候选名单写入 CSV 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "name", "char2", "char3",
        "pinyin_full", "pinyin1", "pinyin2", "pinyin3",
        "tone1", "tone2", "tone3",
        "final1", "final2", "final3",
        "openness1", "openness2", "openness3",
        "strokes1", "strokes2", "strokes3",
        "wuxing1", "wuxing2", "wuxing3", "wuxing_combo",
        "radical2", "radical3",
    ]
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            writer.writerow(c.to_csv_row())

    if verbose:
        print(f"\n  CSV 已写入：{path}  （{len(candidates):,} 条记录）")
